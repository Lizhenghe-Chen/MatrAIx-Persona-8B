"""Replay a two-part AI + choice-history forecast on the frozen tofu study."""
import json
from pathlib import Path

import numpy as np

from final_inputs import HERE, WORK, digest, read
from final_run import load_log
from final_score import bootstrap, compare, score_vectors, stat_forecasts, vectors

OUT = HERE / 'data/final-combined-v1.json'
METHODS = {
    'original': '原版 MatrAIx 单选',
    'output_only': 'MatrAIx 保留完整概率',
    'population': '群体统计',
    'own': '群体统计＋本人两次选择',
    'refusal_only': '统计按本人历史只更新拒买',
    'combined': '本人历史预测买不买，AI 预测买哪款',
}


def replay(*, card_sink=None):
    freeze = read('freeze.json')
    for name in ('people', 'requests'):
        if digest(WORK / f'{name}.json') != freeze[f'{name}_sha256']:
            raise ValueError(f'Frozen input changed: {name}')
    group = read('people.json')['tofu']
    ids = [str(person) for person in group['evaluation']]
    people = group['people']
    desired = {('tofu', person, arm) for person in ids for arm in ('original', 'output_only')}
    requests = {r['request']: (r['study'], str(r['person']), r['arm'])
                for r in read('requests.json') if r['sample'] == 'evaluation'}
    available = {requests[row['request']]: row['probabilities']
                 for row in load_log(WORK / 'final-pro.jsonl')
                 if row['request'] in requests and requests[row['request']] in desired and row['status'] == 'ok'}
    if available.keys() != desired:
        raise ValueError('The replay requires the complete paired tofu cohort')

    rows, forecasts = vectors('tofu', group, ids, available)
    forecasts.update(stat_forecasts(group, ids, rows))
    ai_products = forecasts['output_only'][:, :2]
    mass = ai_products.sum(axis=1, keepdims=True)
    conditional = np.divide(ai_products, mass, out=np.full_like(ai_products, .5), where=mass > 0)
    refusal = forecasts['refusal_only'][:, 2:3]
    forecasts['combined'] = np.concatenate(((1 - refusal) * conditional, refusal), axis=1)

    historical = HERE / 'data/final-replication-v1.json'
    source = json.loads(historical.read_text())
    tofu = next(x['results'] for x in source['studies'] if x['source'].endswith('/22649882'))
    sampling = np.vstack([np.arange(len(ids)), bootstrap(people, ids, False)])
    cards = {entry['card'] for entry in tofu['card_distributions']}
    scores, _, card_results = score_vectors(rows, {key: forecasts[key] for key in METHODS},
                                            [people[key] for key in ids], sampling, cards)
    if len(rows) != tofu['eligible_target_tasks'] or len(card_results) != tofu['scored_cards']:
        raise ValueError('Replay target count or card coverage differs from the frozen study')
    metrics = ('brier', 'tv', 'accuracy', 'incidence', 'conditional')
    for method in METHODS.keys() - {'combined'}:
        for metric in metrics:
            if not np.isclose(np.ravel(scores[method][metric])[0], tofu['scores'][method][metric], atol=1e-12, rtol=0):
                raise ValueError(f'Replay baseline differs: {method}/{metric}')

    if card_sink is not None:
        card_sink.extend(card_results)

    candidate = scores['combined']['brier']
    comparisons = {}
    for ref in ('original', 'output_only', 'population', 'own', 'refusal_only'):
        reference = scores[ref]['brier']
        contrast = compare(reference, candidate, .02, relative=True)
        contrast['relative_improvement'] = contrast['improvement'] / float(reference[0])
        comparisons[ref] = contrast

    return {
        'study': '瑞典豆腐商品选择实验',
        'status': 'exploratory_replay_on_frozen_evaluation_cohort',
        'source_result_sha256': digest(historical),
        'private_pro_log_sha256': digest(WORK / 'final-pro.jsonl'),
        'scoring_code_sha256': digest(Path(__file__).with_name('final_score.py')),
        'people': len(ids),
        'tasks': len(rows),
        'cards': len(card_results),
        'extra_model_calls': 0,
        'bootstrap_replicates': len(sampling) - 1,
        'rule': '拒买概率来自仅按本人记录更新拒买倾向的统计模型，购买条件下的两款概率来自冻结的 AI 概率重新归一。两款概率均为零时平分。',
        'zero_product_mass': int((mass == 0).sum()),
        'scores': {name: {'label': METHODS[name], **{k: float(np.ravel(score[k])[0]) for k in metrics}}
                   for name, score in scores.items()},
        'combined_vs_reference': comparisons,
    }


if __name__ == '__main__':
    OUT.write_text(json.dumps(replay(), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
