"""Post-hoc shoe baseline check with respondent-visible inputs only.

This is a sensitivity analysis on the existing holdout, not a new independent
replication. No LLM requests are made, and the original scores are not changed.
"""
import hashlib
import importlib.metadata
import json
import sqlite3
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder

from retail_shoes_prepare import BACKGROUND, RUN, SEED, SOURCE, load
from retail_shoes_score import ATTRIBUTES, FLAGS, LEVELS, metric_rows, test_frame, training_frame


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = RUN / 'shoes-freeze.json'
    data = json.loads(frozen.read_text())
    keys = data['split']['test']
    assert len(keys) == 240
    assert not set(keys) & set(data['split']['reference'])
    assert digest(SOURCE) == data['source_sha256']
    attributes = [*ATTRIBUTES.values(), *(v[0] for v in FLAGS.values())]
    paired = ['other_' + field for field in attributes]
    fields = [*attributes, *paired, 'profile']
    variants = {'basic': list(BACKGROUND.values())[:2],
                'rich': list(BACKGROUND.values())[:4],
                'attitude': list(BACKGROUND.values())[:6]}
    protocol = {
        'analysis_type': 'post-hoc sensitivity on previously examined test participants',
        'question': 'Does a statistical reference remain useful without attitudes or hidden design labels?',
        'frozen_sample_sha256': digest(frozen), 'source_sha256': digest(SOURCE),
        'seed': SEED, 'training_people': len(data['split']['reference']), 'test_people': len(keys),
        'shared_fields': fields, 'background_by_variant': variants,
        'excluded_inputs': ['design', 'design_eco', 'design_gel', 'participant ID', 'test answers'],
        'encoding': 'one-hot; unseen levels ignored',
        'fit': {'model': 'multinomial logistic regression', 'C': 1, 'max_iter': 250, 'tol': 0.0005},
        'tuning': 'no new hyperparameter search; same regularization as original baseline',
        'bootstrap': '2000 paired respondent resamples within four original design groups',
        'limitations': 'Statistical models learn from separate human ratings; LLM forecasts are not fine-tuned on those ratings.',
    }
    protocol_path = RUN.parent / 'shoes-input-parity-protocol.json'
    if protocol_path.exists():
        assert json.loads(protocol_path.read_text()) == protocol
    else:
        protocol_path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + '\n')
    wave1, _, analysis = load()
    train = training_frame(data, wave1, analysis)
    frame = test_frame(data, keys)
    for table in (train, frame):
        for field in attributes:
            table['other_' + field] = table.groupby('pair', sort=False)[field].transform(lambda s: s.iloc[::-1].to_numpy())
    assert len(train) == len(data['split']['reference']) * 40
    with sqlite3.connect(RUN / 'shoes.sqlite') as db:
        saved = {(person, arm): json.loads(output) for person, arm, output in db.execute(
            'SELECT person,arm,output FROM forecasts WHERE output IS NOT NULL')}
    pred, fits = {}, {}
    for variant, background in variants.items():
        cols = fields + background
        encoder = OneHotEncoder(handle_unknown='ignore')
        x = encoder.fit_transform(train[cols].astype(str))
        model = LogisticRegression(C=1, max_iter=250, tol=0.0005)
        model.fit(x, train.response_num.astype(int))
        assert list(model.classes_) == list(LEVELS)
        pred['statistics_' + variant] = model.predict_proba(encoder.transform(frame[cols].astype(str)))
        fits[variant] = {'iterations': model.n_iter_.tolist(), 'max_iter_reached': bool(max(model.n_iter_) >= 250),
                         'encoded_columns': x.shape[1], 'training_rows': x.shape[0]}
        arm = variant + '_probability'
        pred[arm] = np.array([saved[key, arm][f"{pair['task']}.{shoe}"] for key in keys
                              for pair in data['records'][key]['pairs'] for shoe in (1, 2)])
    n = len(keys)
    truth = np.eye(7)[frame.answer.to_numpy() - 1].reshape(n, 16, 7)
    old = json.loads((RUN.parent / 'shoes-test-score.json').read_text())
    np.testing.assert_allclose(truth.mean(axis=(0, 1)), old['real']['distribution'], atol=1e-12)
    groups = np.array([data['records'][key]['design'] for key in keys])
    rng = np.random.default_rng(SEED)
    indices = np.concatenate([rng.choice(ix, size=(2000, len(ix))) for g in sorted(set(groups))
                              if len(ix := np.flatnonzero(groups == g))], axis=1)
    summary, boot = {}, {}
    for name, flat in pred.items():
        assert flat.shape == (3840, 7) and np.isfinite(flat).all()
        np.testing.assert_allclose(flat.sum(axis=1), 1, atol=1e-10)
        p = flat.reshape(n, 16, 7)
        summary[name] = {'tv_pp': float(50 * abs(p.mean(axis=(0, 1)) - truth.mean(axis=(0, 1))).sum()),
                         'brier': float(((p - truth)**2).sum(axis=2).mean()),
                         'distribution': p.mean(axis=(0, 1)).tolist()}
        boot[name] = metric_rows(p, truth, indices)
        if name in old['summary']:
            for metric in ('tv_pp', 'brier'):
                assert abs(summary[name][metric] - old['summary'][name][metric]) < 1e-10
    comparisons = {}
    for variant in variants:
        llm, stat = variant + '_probability', 'statistics_' + variant
        tv, brier = [a - b for a, b in zip(boot[llm], boot[stat], strict=True)]
        comparisons[variant] = {
            'reference': llm, 'candidate': stat,
            'tv_improvement_pp': summary[llm]['tv_pp'] - summary[stat]['tv_pp'],
            'tv_95_interval': np.quantile(tv, [.025, .975]).tolist(),
            'brier_improvement': summary[llm]['brier'] - summary[stat]['brier'],
            'brier_95_interval': np.quantile(brier, [.025, .975]).tolist(),
        }
    effects = {}
    for attribute, flag in [('Eco-Friendly Materials', 'withEco'), ('Gel Cushioning', 'withGel')]:
        selected = np.array([[a for a, l, r in zip(pair['attributes'], *pair['shoes'], strict=True) if l != r] == [attribute]
                             and data['records'][key]['design'].endswith('constrained')
                             for key in keys for pair in data['records'][key]['pairs']])
        values = frame[flag].astype(int).to_numpy().reshape(-1, 2)
        direction = np.where(selected, np.sign(values[:, 0] - values[:, 1]), 0)
        counts = selected.reshape(n, 8).sum(axis=1)
        def per_person(flat):
            ratings = (flat @ LEVELS).reshape(-1, 2)
            return (direction * (ratings[:, 0] - ratings[:, 1])).reshape(n, 8).sum(axis=1)
        actual = per_person(truth.reshape(-1, 7))
        methods = {}
        for method, flat in pred.items():
            expected = per_person(flat)
            diff = (expected - actual)[indices].sum(axis=1) / counts[indices].sum(axis=1)
            methods[method] = {'effect': float(expected.sum() / counts.sum()),
                               'minus_real_95_interval': np.quantile(diff, [.025, .975]).tolist()}
        effects[attribute] = {'people': int((counts > 0).sum()), 'pairs': int(counts.sum()),
                              'real_effect': float(actual.sum() / counts.sum()), 'methods': methods}
    out = {'analysis_type': protocol['analysis_type'], 'people': n, 'reference_people': len(data['split']['reference']),
           'source_score_sha256': digest(RUN.parent / 'shoes-test-score.json'),
           'protocol_sha256': digest(protocol_path), 'runner_sha256': digest(Path(__file__)),
           'summary': summary, 'comparisons': comparisons, 'controlled_attribute_effects': effects,
           'fit_checks': fits, 'versions': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'pyreadr', 'scikit-learn']},
           'checks': {'test_people_unchanged': True, 'splits_disjoint': True, 'source_hash_verified': True,
                      'original_llm_metrics_reproduced': True, 'llm_requests': 0}}
    (RUN.parent / 'shoes-input-parity-score.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    np.savez_compressed(RUN / 'shoes-input-parity-predictions.npz', **pred)
    print(json.dumps({'summary': {k: {m: v[m] for m in ['tv_pp','brier']} for k,v in summary.items()},
                      'comparisons': comparisons, 'fits': fits}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
