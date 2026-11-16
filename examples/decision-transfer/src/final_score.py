"""Score the final survey and choice experiment from private frozen inputs."""
from collections import Counter, defaultdict
import json

import numpy as np
from scipy.optimize import minimize
from scipy.special import log_softmax, softmax

from final_inputs import HERE, SEED, WORK, digest, read
from final_run import cost_of, load_log

LABELS = {'nhanes': '美国 CDC 食品标签问卷', 'tofu': '瑞典豆腐商品选择实验'}
SOURCE = {'nhanes': 'https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/CBQPFA_J.htm',
          'tofu': 'https://zenodo.org/records/22649882'}
METHOD = {'original': '原生问卷单选', 'argmax': '概率只留最高项', 'output_only': '直接保留各项概率',
          'uniform': '等概率参考', 'population': '训练侧群体统计', 'own': '群体统计＋本人两次选择',
          'other': '群体统计＋他人两次选择', 'refusal_only': '只更新本人拒买倾向',
          'pilot': '直接用二十份真人试答', 'pilot_uniform': '试答与等概率各半',
          'pilot_ai': '试答与 AI 概率各半'}
PRICE = [15, 20, 25, 30, 35, 40, 50, 60]
PARTICLE_SHIFT = 2.0
N_BOOT = 2000
OUT = HERE / 'data/final-replication-v1.json'


def bootstrap(people, ids, stratified):
    rng = np.random.default_rng(SEED + 3)
    groups = defaultdict(list)
    for i, person in enumerate(ids):
        groups[people[person]['sampling_stratum'] if stratified else 0].append(i)
    return np.concatenate([rng.choice(group, size=(N_BOOT, len(group))) for group in groups.values()], axis=1)


def compare(reference, candidate, threshold, *, relative):
    base, change = reference[0], reference - candidate
    low, high = np.quantile(change[1:], [.025, .975])
    gain = float(change[0])
    passes = (gain / base if relative and base else gain) >= threshold and low > 0
    return {'improvement': gain, 'ci95': [float(low), float(high)], 'passed': bool(passes)}


def as_row(label, result, relative_base=None):
    gain, (low, high) = result['improvement'], result['ci95']
    rel = '' if relative_base is None else f'（{gain / relative_base:+.1%}）'
    return [label, f'{gain:+.3f}{rel}', f'[{low:+.3f}, {high:+.3f}]',
            '达到门槛' if result['passed'] else '未达到门槛']


def vectors(study, group, ids, runs):
    people = group['people']
    prediction = defaultdict(dict)
    rows = []
    for i, person in enumerate(ids):
        for task in people[person]['tasks']:
            qid = task['question']['id']
            n = len(task['question']['options'])
            key = len(rows)
            rows.append((i, task))
            prediction['uniform'][key] = np.full(n, 1 / n)
            if runs:
                orig = runs[(study, person, 'original')][qid]
                prob = runs[(study, person, 'output_only')][qid]
                prediction['original'][key] = orig
                prediction['output_only'][key] = prob
                prediction['argmax'][key] = np.eye(n)[np.argmax(prob)]
    return rows, {name: np.asarray(list(p.values())) for name, p in prediction.items()}


def product_features(task):
    features = []
    for position, (made, soy, organic, price) in enumerate(task['attrs']):
        features.append([0, position, made == 2, made == 3, soy == 2, soy == 3,
                         organic == 1, PRICE[price - 1] / 20])
    features.append([1, 0, 0, 0, 0, 0, 0, 0])
    return np.asarray(features, dtype=float)


def stat_forecasts(group, ids, rows):
    people = group['people']
    train = [task for key in group['training'] for task in people[str(key)]['history'] + people[str(key)]['tasks']]
    x = np.stack([product_features(task) for task in train])
    y = np.eye(3)[[task['answer'] for task in train]]

    def objective(beta):
        utilities = x @ beta
        value = -(log_softmax(utilities, axis=1) * y).sum(axis=1).mean()
        grad = np.einsum('na,nak->k', softmax(utilities, axis=1) - y, x) / len(x)
        return value + .01 * (beta @ beta), grad + .02 * beta

    fit = minimize(objective, np.zeros(x.shape[-1]), jac=True, method='L-BFGS-B',
                   bounds=[(None, None)] * (x.shape[-1] - 1) + [(None, 0)])
    if not fit.success:
        raise ValueError(f'Statistical fit failed: {fit.message}')
    beta = fit.x
    target = np.stack([product_features(task) for _, task in rows])
    pred = {'population': softmax(target @ beta, axis=1)}
    donor_rng = np.random.default_rng(SEED + 8)
    pools = defaultdict(list)
    for i, key in enumerate(ids):
        pools[int(people[key]['age'] in ('65-74', '75-84', '85+'))].append(i)
    donor = np.arange(len(ids))
    for members in pools.values():
        if len(members) < 2:
            raise ValueError('Not enough controls in a cohort donor stratum')
        permuted = donor_rng.permutation(members)
        donor[permuted] = np.roll(permuted, 1)
    t_ids = np.asarray([i for i, _ in rows])
    known = [people[key]['history'] for key in ids]
    known_x = np.asarray([[product_features(task) for task in person] for person in known])
    known_y = np.eye(3)[[[t['answer'] for t in person] for person in known]]

    def update(axes):
        directions = PARTICLE_SHIFT * np.eye(len(beta))[axes]
        particles = beta + np.vstack([np.zeros_like(beta), directions, -directions])
        particles[:, -1] = np.minimum(0, particles[:, -1])
        probs = softmax(target @ particles.T, axis=1)
        evidence = (log_softmax(known_x @ particles.T, axis=2) * known_y[..., None]).sum(axis=(1, 2))
        weights = softmax(evidence, axis=1)
        return (np.einsum('rat,rt->ra', probs, weights[t_ids]),
                np.einsum('rat,rt->ra', probs, weights[donor[t_ids]]))

    pred['own'], pred['other'] = update(list(range(len(beta))))
    pred['refusal_only'], _ = update([0])
    return pred


def score_vectors(rows, predictions, persons, sampling, estimable):
    truth = np.eye(next(iter(predictions.values())).shape[1])[[task['answer'] for _, task in rows]]
    idx = np.asarray([person for person, _ in rows])
    person_weights = np.asarray([p['weight'] for p in persons], dtype=float)
    counts = np.bincount(idx, minlength=len(persons))
    sample_counts = np.stack([np.bincount(sample, minlength=len(persons)) for sample in sampling])
    weighted = sample_counts * person_weights
    scorer_weights = weighted / weighted.sum(axis=1, keepdims=True)
    task_weights = person_weights[idx]
    groups = defaultdict(list)
    for n, (_, task) in enumerate(rows):
        groups[task['card']].append(n)
    cards = {}
    for card, indices in sorted(groups.items()):
        indices = np.asarray(indices)
        repeats = np.bincount(idx[indices])
        if card in estimable and np.count_nonzero(repeats) >= 20:
            cards[card] = indices, repeats[idx[indices]]


    def card_tv(matrix, point_only=False):
        relevant_weights = weighted[:1] if point_only else weighted
        values = []
        for indices, repeats in cards.values():
            weights = relevant_weights[:, idx[indices]] / repeats
            denom = weights.sum(axis=1)
            dissimilarity = abs(weights @ (matrix[indices] - truth[indices])).sum(axis=1)
            values.append(np.divide(50 * dissimilarity, denom, out=np.zeros_like(denom), where=denom > 0))
        return np.asarray(values).mean(axis=0) if values else None

    results = {}
    for name, matrix in predictions.items():
        if not np.all(np.isfinite(matrix)) or not np.allclose(matrix.sum(axis=1), 1) or np.any(matrix < 0):
            raise ValueError('Illegal probability in score input')
        raw_loss = np.square(matrix - truth).sum(axis=1)
        correct = matrix.argmax(axis=1) == truth.argmax(axis=1)
        results[name] = {
            'brier': scorer_weights @ (np.bincount(idx, raw_loss, minlength=len(persons)) / counts),
            'accuracy': float(scorer_weights[0] @ (np.bincount(idx, correct, minlength=len(persons)) / counts)),
            'tv': card_tv(matrix),
            'recall': [float(task_weights[(truth[:, j] == 1) & correct].sum() / task_weights[truth[:, j] == 1].sum())
                       if np.any(truth[:, j] == 1) else None for j in range(truth.shape[1])],
        }
        if truth.shape[1] == 3:
            # Outside option is the third recorded option. Conditional scores are for actual purchasers.
            purchase = truth[:, 2] == 0
            mass = matrix[purchase, :2].sum(axis=1, keepdims=True)
            conditional = np.divide(matrix[purchase, :2], mass, out=np.full_like(matrix[purchase, :2], .5),
                                    where=mass > 0)
            results[name]['incidence'] = float(np.square(matrix[:, 2] - truth[:, 2]).mean())
            results[name]['conditional'] = float(np.square(conditional - truth[purchase, :2]).sum(axis=1).mean())
            results[name]['conditional_zero_mass'] = int((mass == 0).sum())
    card_groups = []
    for card, (indices, repeats) in cards.items():
        weights = task_weights[indices] / repeats
        card_groups.append({
            'card': card, 'people': int(np.unique(idx[indices]).size),
            'options': [option['label'] for option in rows[indices[0]][1]['question']['options']],
            'real': np.average(truth[indices], axis=0, weights=weights).tolist(),
            'model': {name: np.average(matrix[indices], axis=0, weights=weights).tolist()
                      for name, matrix in predictions.items()},
        })
    return results, card_tv, card_groups


def pilot_sensitivity(group, ids, rows, predictions, card_tv):
    rng = np.random.default_rng(SEED + 10)
    people = group['people']
    task_weights = np.asarray([people[ids[i]]['weight'] for i, _ in rows])
    cards = defaultdict(list)
    for i, (_, task) in enumerate(rows):
        cards[task['card']].append(i)
    model = {card: np.average(predictions['output_only'][indices], weights=task_weights[indices], axis=0)
             for card, indices in cards.items()}
    ai = np.asarray([model[task['card']] for _, task in rows])
    reps = {}
    effects = defaultdict(list)
    for repeat in range(200):
        sample = rng.choice(group['training'], size=20, replace=False)
        counts = defaultdict(lambda: np.zeros(6))
        for pid in sample:
            for task in people[str(pid)]['tasks']:
                counts[task['card']][task['answer']] += 1
        pilot = np.asarray([counts[task['card']] / 20 for _, task in rows])
        mats = {'pilot': pilot, 'pilot_uniform': .5 * (pilot + predictions['uniform']), 'pilot_ai': .5 * (pilot + ai)}
        if repeat == 0:
            reps = {name: card_tv(mat) for name, mat in mats.items()}
        else:
            # Alternate pilot draws show sensitivity of the point estimates at the fixed evaluation sample.
            for name, mat in mats.items():
                effects[name].append(float(card_tv(mat, point_only=True)[0]))
    improvement = {name: compare(reps[name], reps['pilot_ai'], 2, relative=False) for name in ('pilot', 'pilot_uniform')}
    sensitivity = {name: float(np.mean(np.asarray(effects[name]) > np.asarray(effects['pilot_ai'])))
                   for name in improvement}
    return {'scores': {name: float(x[0]) for name, x in reps.items()}, 'contrasts': improvement,
            'alternate_draws': 199, 'share_ai_better': sensitivity,
            'recommend': all(c['passed'] for c in improvement.values())}


def score_study(study, group, available):
    people = group['people']
    ids = [str(i) for i in group['evaluation']]
    matched_ids = [key for key in ids if all((study, key, arm) in available for arm in ('original', 'output_only'))]
    completion = {arm: sum((study, key, arm) in available for key in ids) for arm in ('original', 'output_only')}
    qualifies = len(matched_ids) / len(ids) >= .98
    evaluate_ids = matched_ids if qualifies else ids
    rows, predictions = vectors(study, group, evaluate_ids, available if qualifies else {})
    estimable = {card for card, count in Counter(card for key in ids for card in {t['card'] for t in people[key]['tasks']}).items()
                 if count >= 20}
    if study == 'tofu':
        predictions.update(stat_forecasts(group, evaluate_ids, rows))
    sampling = np.vstack([np.arange(len(evaluate_ids)), bootstrap(people, evaluate_ids, study == 'nhanes')])
    scores, card_tv, cards = score_vectors(rows, predictions, [people[key] for key in evaluate_ids], sampling, estimable)
    contrasts = {}
    if qualifies:
        for reference, candidate in (('original', 'argmax'), ('argmax', 'output_only'), ('original', 'output_only')):
            contrasts[f'{reference}__{candidate}'] = {
                'choice': compare(scores[reference]['brier'], scores[candidate]['brier'], .02, relative=True),
                'group': compare(scores[reference]['tv'], scores[candidate]['tv'], 2, relative=False)}
    if study == 'tofu':
        for reference in ('population', 'other'):
            contrasts[f'{reference}__own'] = {'choice': compare(scores[reference]['brier'], scores['own']['brier'], .02, relative=True)}
    pilot = pilot_sensitivity(group, evaluate_ids, rows, predictions, card_tv) if study == 'nhanes' and qualifies else None
    output = {name: {k: float(v[0]) if isinstance(v, np.ndarray) else v for k, v in result.items()}
              for name, result in scores.items()}
    return {'scores': output, 'contrasts': contrasts, 'pilot': pilot, 'completion': completion,
            'paired_model_people': len(matched_ids), 'scored_people': len(evaluate_ids), 'scored_cards': len(cards),
            'card_distributions': cards,
            'eligible_target_tasks': len(rows), 'stat_training_people': len(group['training']) if study == 'tofu' else None}


def presentation(study, result):
    scores = result['scores']
    name = LABELS[study]
    group = study == 'nhanes'
    note = ('固定五道食品标签题。只评估可还原的无手卡、无包装分支，20 岁及以上。用官方饮食访谈权重计算该分支成绩。'
            if group else '只评估瑞典研究的无干预组。两次已知选择来自原始题序，完全相同的卡片从其后目标题排除。')
    if not group:
        note += ' 二十名试答者不足以覆盖每张轮转题卡，因此本组只评价原流程和本人记录。'
    note += f" 可配对的 Pro 评估为 {result['paired_model_people']}/96 人。每卡至少 20 名评估者的题卡有 {result['scored_cards']} 张。"
    if result['paired_model_people'] < 95:
        note += '模型结果未达到 98% 完成门槛。'
    figures = []
    if 'original' in scores:
        figures.append({'title': f"{name}，群体比例", 'unit': '百分点',
                        'rows': [[METHOD[k], scores[k]['tv']] for k in ('original', 'argmax', 'output_only', 'uniform')],
                        'maximum': 100})
    if not group:
        figures.append({'title': f"{name}，同一批预测题", 'unit': '个人选择概率误差｜Brier',
                        'rows': [[METHOD[k], v['brier']] for k, v in scores.items()],
                        'maximum': 2, 'digits': 3})
    if result['pilot']:
        pilot = result['pilot']
        figures.append({'title': f"{name}，固定抽出的 20 位真人试答", 'unit': '群体比例误差｜百分点',
                        'rows': [[METHOD[k], v] for k, v in pilot['scores'].items()],
                        'maximum': 50})
        note += ' ' + ('本次混合通过两条采用门槛。' if pilot['recommend'] else '本次混合未同时通过两条采用门槛。')
        note += (f" 另 199 次重抽试答人中，AI 混合优于直接试答的比例为 {pilot['share_ai_better']['pilot']:.1%}，"
                 f"优于等概率混合的比例为 {pilot['share_ai_better']['pilot_uniform']:.1%}。")
    headers = ['方法','群体误差','个人概率误差','答对率']
    if not group:
        headers += ['买不买误差', '买哪款误差', '拒买召回']
    rows = [[METHOD[k], '—' if v['tv'] is None else f"{v['tv']:.2f}", f"{v['brier']:.3f}", f"{v['accuracy']:.1%}",
             *([] if group else [f"{v['incidence']:.3f}", f"{v['conditional']:.3f}", ('—' if v['recall'][2] is None else f"{v['recall'][2]:.1%}")])]
            for k, v in scores.items()]
    pair_rows = []
    for name, effects in result['contrasts'].items():
        r, c = name.split('__')
        label = f'{METHOD[r]} → {METHOD[c]}'
        for kind, effect in effects.items():
            brier = kind == 'choice'
            pair_rows.append(as_row(label + ('（个人）' if brier else '（群体）'), effect,
                                    scores[r]['brier'] if brier else None))
    if result['pilot']:
        pair_rows.extend(as_row(METHOD[k] + ' → ' + METHOD['pilot_ai'], x)
                         for k, x in result['pilot']['contrasts'].items())
    protocol = {'headers': headers, 'rows': rows}
    if group:
        protocol_extra = [{'headers': ['方法', '总是', '通常', '有时', '很少', '从不', '从未见过'],
                           'rows': [[METHOD[k], *['—' if x is None else f'{x:.1%}' for x in v['recall']]]
                                    for k, v in scores.items()]}]
    else:
        protocol_extra = []
    question = next((c for c in result['card_distributions'] if c['card'] == 'CBQ700'), None)
    if question and 'original' in scores:
        distributions = [['总是','通常','有时','很少','从不','从未见过'],
                         question['real'], question['model']['original'], question['model']['output_only']]
        protocol_extra.append({'headers': ['例题：买食品会看保质日期吗？', '真人比例', '原单选比例', '保留概率后'],
                               'rows': [[label, f'{real:.1%}', f'{original:.1%}', f'{probability:.1%}']
                                        for label, real, original, probability in zip(*distributions, strict=True)]})
    return {'label': LABELS[study], 'note': note, 'source': SOURCE[study], 'figures': figures,
            'tables': [protocol, *protocol_extra, {'headers': ['比较', '改善', '95% 区间', '结论'], 'rows': pair_rows}],
            'results': result}


def main():
    freeze = read('freeze.json')
    if any(digest(WORK / f'{name}.json') != freeze[f'{name}_sha256'] for name in ('people', 'requests')):
        raise ValueError('Private input does not match manifest')
    people = read('people.json')
    requests = {item['request']: item for item in read('requests.json')}
    available = {}
    logs = {}
    for provider in ('qwen', 'pro'):
        log = load_log(WORK / f'final-{provider}.jsonl')
        logs[provider] = {'attempts': len(log), 'successful': sum(row['status'] == 'ok' for row in log),
                          'budget_estimate_usd': sum(cost_of(provider, row['usage']) for row in log),
                          'failure_reasons': dict(Counter(row.get('reason', 'unknown') for row in log if row['status'] != 'ok')),
                          'identities': sorted({json.dumps(row['identity'], sort_keys=True) for row in log if 'identity' in row})}
        if provider != 'pro':
            continue
        for row in log:
            if row['status'] != 'ok' or row['sample'] != 'evaluation':
                continue
            item = requests[row['request']]
            available[(item['study'], str(item['person']), item['arm'])] = row['probabilities']
    output = {'freeze': freeze, 'run': logs, 'scorer_sha256': digest(HERE / 'src/final_score.py'),
              'studies': [presentation(name, score_study(name, group, available))
                                                       for name, group in people.items()]}
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
