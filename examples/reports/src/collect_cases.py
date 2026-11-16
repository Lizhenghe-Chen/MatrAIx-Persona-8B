"""Publish only per-question aggregate shares from the validated local checkpoints."""
import json
import math
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

EXAMPLES = Path(__file__).resolve().parents[2]
STAGE = EXAMPLES / 'decision-transfer'
LAB = EXAMPLES / 'sim-to-real/decision_lab'
OUT = EXAMPLES / 'reports/data/question-cases-v1.json'
sys.path.insert(0, str(STAGE / 'src'))

from final_combined import replay  # noqa: E402
from final_inputs import CDC_ITEMS, CONTEXT, FREQUENCY, SEED, WORK, digest, read  # noqa: E402
from decision_lab.cross_study import formal  # noqa: E402
from decision_lab.cross_study.scoring import card_error, person_brier, weighted_mean  # noqa: E402

BASELINE = 'MatrAI X 项目（单选）'
FORMAL_RESULT = LAB / 'reports/cross-study-v1/formal-results.json'
PER_CARD = LAB / 'reports/cross-study-v1/per-card.json'
REPLICATION = STAGE / 'data/final-replication-v1.json'
COMBINED = STAGE / 'data/final-combined-v1.json'
ARM_COMMON = {
    'real': ('真人实测', '真人', '实际受访者的留出答案。'),
    'original': (BASELINE, 'MatrAI X\n项目单选', '用项目的原生问卷指令，每个画像选一项，再汇总选择比例。'),
    'output_only': ('A · 仅改为概率', 'A 保留概率', '同一原生指令。每个画像给出全部选项的概率，按同样口径汇总。'),
}
HISTORICAL_ARMS = ARM_COMMON | {
    'prompt_only': ('仅改提示', '改提示', '把指令改为预测画像代表的人的选择，仍只选一项。'),
    'optimized': ('改提示＋保留概率', '改提示＋概率', '把指令改为预测该画像代表的人的选择，同时输出各选项的概率。'),
}
# Cases chosen by topic and question identity, independently of the observed improvement.
HISTORICAL_EXAMPLES = (
    ('v1', 'pew13', 'SHOP12', 'Pew 购物与评价', '购物前会看其他人的评价吗？',
     'https://www.pewresearch.org/internet/dataset/american-trends-panel-wave-13/'),
    ('wide-v1', 'pew111', 'SHOP4', 'Pew 网购与到店', '更喜欢网上买，还是到实体店买？',
     'https://www.pewresearch.org/internet/dataset/american-trends-panel-wave-111/'),
    ('external-v2', 'openecommerce', 'amazon_frequency', 'Open eCommerce 线上购物', '多久用一次亚马逊？', None),
    ('v1', 'shed', 'INF3_a', '美国家庭应对涨价', '过去一年有没有因涨价而改买更便宜的商品？',
     'https://www.federalreserve.gov/consumerscommunities/shed_data.htm'),
    ('v1', 'pew168', 'OSCAM_PLAT_d', 'Pew 网络诈骗风险', '购物网站或应用上的网络诈骗和攻击有多严重？',
     'https://www.pewresearch.org/dataset/american-trends-panel-wave-168/'),
    ('v1', 'anes', 'V241267', '美国公共支出', '联邦用于加强边境安全的支出该增、该减，还是保持？',
     'https://electionstudies.org/data-center/2024-time-series-study/'),
    ('wide-v1', 'packaging', 'block1_card1', '美国啤酒包装与拒买', '这两款啤酒，你会买哪款？',
     'https://itemresponsewarehouse.org/tables/staples_2020_beer_eco_labels/'),
    ('wide-v1', 'german', 'german_task1', '德国番茄包装', '买一公斤番茄时，你会选哪种包装？', None),
    ('wide-v1', 'radiant', 'radiant_a937d59920da', '西班牙悬挂番茄', '这两种悬挂番茄，你会买哪种？',
     'https://doi.org/10.5281/zenodo.15420092'),
)
OPTION_TRANSLATIONS = {
    'Always or almost always': '总是或几乎总是', 'Sometimes': '有时', 'Never': '从不',
    'Online': '网上买', 'Physical store': '实体店买', 'Yes': '是', 'No': '否',
    '5 - 10 times per month': '每月 5 至 10 次', 'Less than 5 times per month': '每月少于 5 次',
    'More than 10 times per month': '每月多于 10 次',
    'Major problem': '严重问题', 'Minor problem': '小问题', 'Not a problem': '没有问题', 'Not sure': '不确定',
    'Increased': '增加', 'Decreased': '减少', 'Kept the same': '保持不变',
}
ATTRIBUTE_TRANSLATIONS = {
    'packaging': '包装', 'water_conserving': '节水', 'energy_conserving': '节能',
    'waste_reduction': '减废', 'local': '本地生产', 'price': '价格',
    'Packaging material': '材料', 'biodegradability': '降解性', 'shelf life': '保质期',
    'variety': '品种', 'cultural value': '文化价值', 'access': '销售渠道',
    'label': '标签', 'place of production': '产地', 'cost': '单价',
}
VALUE_TRANSLATIONS = {
    'Bottle': '瓶装', 'Can': '罐装', 'Yes': '是', 'No': '否',
    'Bio-based': '生物基', 'Fossil-based': '化石原料', 'Biodegradable': '可降解', 'Non-biodegradable': '不可降解',
    '3 days': '3 天', '5 days': '5 天', '7 days': '7 天',
    'Commercial variety': '商业品种', 'Underutilised variety': '较少利用的品种',
    'With cultural value': '有', 'Without cultural value': '无', 'Supermarket': '超市',
    'Speciality food shop': '专门食品店', 'Short food supply chain': '短食品供应链',
    'With label': '有标签', 'Without label': '无标签',
    'Locally (your province)': '本省', 'Elsewhere in Spain': '西班牙其他省份', 'Outside Spain': '西班牙以外',
}


def fractions(actual, expected):
    return len(actual) == len(expected) and all(abs(a - b) < 1e-10 for a, b in zip(actual, expected))


def arms(vectors, metadata):
    output = []
    for key, vector in vectors.items():
        shares = [float(x) for x in vector]
        if abs(sum(shares) - 1) > 1e-8 or any(not math.isfinite(x) or not 0 <= x <= 1 for x in shares):
            raise ValueError('Invalid share in aggregate case')
        name, short, method = metadata[key]
        output.append({'key': key, 'label': name, 'short': short, 'method': method, 'shares': shares})
    return output


def formal_shares(frozen):
    formal.select_plan('v1')
    published = json.loads(FORMAL_RESULT.read_text())
    plan = json.loads(formal.SPEC_FILE.read_text())
    source_db = formal.DB
    wal = Path(f'{source_db}-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError('Formal checkpoint has a pending WAL')
    if digest(formal.FORMS) != plan['jobs_sha256'] or plan['jobs_sha256'] != published['jobs_sha256']:
        raise ValueError('Historical frozen jobs changed')
    # Reading SQLite directly can touch its shared-memory file. Work on a private copy.
    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / 'formal.sqlite'
        shutil.copyfile(source_db, local)
        if digest(local) != digest(source_db):
            raise ValueError('Private checkpoint copy changed')
        try:
            formal.DB = local
            _, studies, execution = formal._cases()
        finally:
            formal.DB = source_db
    if execution['missing_calls'] or execution['states'] != published['execution']['states']:
        raise ValueError('Historical checkpoint completeness changed')
    results = {}
    for phase, study, code, *_ in HISTORICAL_EXAMPLES:
        if phase != 'v1':
            continue
        for arm in frozen['arms']:
            def vector_for(question, case):
                return case['predictions'][arm][str(question['id'])]

            scores = published['studies'][study]['results']['arms'][arm]
            calculated = weighted_mean([(person_brier(c, vector_for), c['weight']) for c in studies[study]])
            error, _, _ = card_error(studies[study], vector_for)
            if not (math.isclose(calculated, scores['brier'], abs_tol=1e-10)
                    and math.isclose(error, scores['card_tv_pp'], abs_tol=1e-10)):
                raise ValueError('Historical four-arm scores do not reconcile')
        raw = next(r for r in frozen['studies'][study]['questions'] if r['question'] == code)
        ids = [item['id'] for item in raw['options']]
        weights = []
        predictions = {name: [] for name in HISTORICAL_ARMS}
        for row in studies[study]:
            if code not in row['truth']:
                continue
            weights.append(row['weight'])
            predictions['real'].append([float(row['truth'][code] == opt) for opt in ids])
            for name in predictions.keys() - {'real'}:
                predictions[name].append(row['predictions'][name][code])
        proportions = {name: np.average(vectors, weights=weights, axis=0).tolist()
                       for name, vectors in predictions.items()}
        if len(weights) != raw['people'] or not all(fractions(proportions[arm], raw[src]) for arm, src in (
            ('real', 'truth'), ('original', 'original'), ('optimized', 'optimized'),
        )):
            raise ValueError('Four-arm reconstruction differs from published cards')
        results[code] = proportions
    return results, {
        'private_formal_checkpoint_sha256': digest(source_db),
        'formal_jobs_sha256': published['jobs_sha256'],
        'formal_scoring_spec_sha256': published['spec_sha256'],
        'formal_verification': 'Jobs match and the four arms of each selected v1 study reconcile. The stored spec file hash and the hash logged at scoring differ.',
    }


def product_description(option):
    attributes = [part.split(': ', 1) for part in option.split(', ')]
    return ' · '.join(f'{ATTRIBUTE_TRANSLATIONS[name]} {VALUE_TRANSLATIONS.get(value, value)}'
                      for name, value in attributes)


def historical_cases(history):
    shares, provenance = formal_shares(history['v1'])
    cases = []
    for phase, study, code, name, title, source in HISTORICAL_EXAMPLES:
        record = history[phase]['studies'][study]
        raw = next(card for card in record['questions'] if card['question'] == code)
        if not raw['estimable'] or not raw['original']:
            raise ValueError(f'Historical case lacks paired group distributions: {code}')
        vectors = shares.get(code, {name: raw[field] for name, field in (
            ('real', 'truth'), ('original', 'original'), ('optimized', 'optimized'))})
        original_options = [option['label'] for option in raw['options']]
        product = study in {'packaging', 'german', 'radiant'}
        if product:
            translated = [f'款 {i + 1}' for i in range(len(original_options) - 1)] + ['都不买']
        else:
            translated = [OPTION_TRANSLATIONS[option] for option in original_options]
        old_page = f'../sim-to-real/reports/cards.html#s-{study}'
        case = {
            'id': code, 'study_id': study, 'title': title, 'study': name, 'family': name,
            'n': raw['people'], 'prompt': raw['prompt'], 'option_labels': translated,
            'original_options': original_options, 'source': source or old_page,
            'fixed': '同一批评估者、相同画像、题目、选项和 DeepSeek Pro。各组采用同一份评分权重。',
            'changed': ('对照分别更换提示词或输出方式，再测试两个改法合用。' if phase == 'v1' else
                        '同时改成预测画像所代表的人会怎么选，并给出各选项概率。这个对照只运行了项目单选与两个改法合用。'),
            'compare': 'optimized', 'arms': arms(vectors, HISTORICAL_ARMS),
        }
        if product:
            case['alternatives'] = [product_description(option) for option in original_options[:-1]]
        cases.append(case)
    return cases, provenance


def nhanes_cases(report):
    freeze = read('freeze.json')
    if digest(WORK / 'people.json') != freeze['people_sha256']:
        raise ValueError('Frozen NHANES participants changed')
    results = report['studies'][0]['results']
    group = read('people.json')['nhanes']
    pilot_people = np.random.default_rng(SEED + 10).choice(group['training'], size=20, replace=False)
    groups = {}
    for card in results['card_distributions']:
        key = card['card']
        count = Counter(next(t['answer'] for t in group['people'][str(person)]['tasks'] if t['card'] == key)
                        for person in pilot_people)
        pilot = np.asarray([count[i] / len(pilot_people) for i in range(len(card['options']))])
        mixed = (pilot + np.asarray(card['model']['output_only'])) / 2
        uniform = (pilot + np.asarray(card['model']['uniform'])) / 2
        groups[key] = {
            'real': card['real'], 'original': card['model']['original'], 'output_only': card['model']['output_only'],
            'pilot': pilot, 'pilot_uniform': uniform, 'pilot_ai': mixed,
        }
    for key in ('pilot', 'pilot_uniform', 'pilot_ai'):
        errors = [50 * sum(abs(x - y) for x, y in zip(g[key], g['real'])) for g in groups.values()]
        if not math.isclose(np.mean(errors), results['pilot']['scores'][key], abs_tol=1e-10):
            raise ValueError('Pilot reconstruction differs from the published comparison')
    metadata = ARM_COMMON | {
        'pilot': ('B · 20 份真人试答', 'B 直接数试答', '直接统计同一批 20 名试答者的回答；这 20 人不在评估样本中。'),
        'pilot_uniform': ('试答＋等概率参照', '试答＋等分', '把试答占比与每个选项等概率各取一半。同权重参照，检验 AI 有没有额外信息。'),
        'pilot_ai': ('C · 试答＋AI 概率', 'C 试答＋AI', '使用 B 的同一批 20 人和 A 的概率预测，两者各占 50%。'),
    }
    labels = ['总是', '大多数时候', '有时', '很少', '从不', '从未见过']
    source = 'https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/CBQPFA_J.htm'
    titles = {
        'CBQ700': '买食品会看包装上的日期吗？',
        'DBQ750': '买食品会看营养成分表吗？',
        'DBQ760': '买食品会看配料表吗？',
        'DBQ770': '买食品会看标签上每份的分量吗？',
        'DBQ780': '买食品会参考包装上的健康功效说明吗？',
    }
    if set(titles) != set(groups):
        raise ValueError('Food-label case titles must cover all frozen questions')
    return [{
        'id': card['card'], 'title': titles[card['card']], 'study': '2017–2018 年美国 CDC 食品标签调查',
        'study_id': 'nhanes', 'family': '美国 CDC 食品标签', 'n': card['people'], 'source': source,
        'prompt': CDC_ITEMS[card['card']] + FREQUENCY,
        'option_labels': labels, 'original_options': card['options'],
        'fixed': '按同样的评估题面、选项和 96 名有效评估者加权判分。两种 AI 作答均固定 DeepSeek Pro、画像和原生问卷提示。',
        'changed': 'A 只改变输出。B 增加独立的 20 份真人试答。C 合并 A 和这同一批试答；等分参照使用相同权重。',
        'note': '题面为冻结实验中使用的电话访问分支。真人评估占比加权，20 份试答按人数直接计数。',
        'compare': 'output_only', 'arms': arms(groups[card['card']], metadata),
    } for card in results['card_distributions']]


def tofu_cases(report):
    cards = []
    checked = replay(card_sink=cards)
    if checked != json.loads(COMBINED.read_text()):
        raise ValueError('The replay differs from the frozen combination result')
    known = {card['card']: card for card in report['studies'][1]['results']['card_distributions']}
    if set(known) != {card['card'] for card in cards}:
        raise ValueError('The combination must use the same cards')
    metadata = ARM_COMMON | {
        'population': ('B · 群体统计', 'B 群体统计', '从独立训练侧的 261 人选择学习，掌握价格、产地、种植方式等属性规律。'),
        'own': ('C · 群体统计＋本人记录', 'C 统计＋记录', '在群体统计基础上，用本人此前两次选择更新各项偏好。'),
        'refusal_only': ('统计＋本人记录（只更新拒买）', '统计只改拒买', '本人记录只用于更新都不买的概率。假如会买，选哪款用群体统计。'),
        'combined': ('合用 · 本人记录判断买不买＋AI 选款', '合用 AI 选款', '与只更新拒买的统计组共用买不买的概率。假如会买，改用 AI 给出的 A／B 相对概率。'),
    }
    results = []
    for i, card in enumerate(sorted(cards, key=lambda c: (-c['people'], c['card'])), 1):
        base = known[card['card']]
        if not fractions(card['real'], base['real']) or card['options'] != base['options'] or card['people'] != base['people']:
            raise ValueError('The per-card reference differs from the frozen comparison')
        vectors = {'real': card['real'],
                   **{key: card['model'][key] for key in ('original', 'output_only', 'population', 'own', 'refusal_only', 'combined')}}
        if not all(fractions(vector, base['model'][key]) for key, vector in vectors.items() if key in base['model']):
            raise ValueError('Replayed per-card shares differ from the frozen comparison')
        attrs = json.loads(card['card'])
        countries = ('瑞典', '其他欧盟国家', '欧盟外国家')
        price = (15, 20, 25, 30, 35, 40, 50, 60)
        products = [
            {'choice': label, 'origin': countries[made - 1], 'soy': countries[soy - 1],
             'method': '有机' if organic == 1 else '非有机常规', 'price': f'{price[cost - 1]} SEK'}
            for label, (made, soy, organic, cost) in zip(('款 1', '款 2'), attrs)
        ]
        results.append({
            'id': f'tofu-{i}', 'title': f'两款 400 克豆腐，你会买哪款？（题卡 {i}）',
            'study': '2021 年瑞典豆腐选择实验', 'study_id': 'tofu', 'family': '瑞典豆腐选择', 'n': card['people'],
            'prompt': CONTEXT['tofu'] + '\n\nVilken produkt skulle du föredra? Ta hänsyn till priset när du gör ditt val. Var realistisk i ditt beslut och välj endast den variant som du skulle vara beredd att betala för i en verklig butik.',
            'option_labels': ['款 1', '款 2', '两款都不买'], 'original_options': card['options'],
            'products': products, 'source': 'https://zenodo.org/records/22649882',
            'fixed': '共享同一张题卡、价格、选项和该卡实际有效受访者。AI 两组固定 DeepSeek Pro、原生问卷提示和同一批画像。',
            'changed': '统计组额外用独立训练侧数据，本人记录组还用每人的前两次真实选择。合用与只更新拒买的统计组使用同一批真人资料，只改变选款算法。',
            'note': '这是根据问卷情境作出的假设选择。图中的合用分布来自同一批受访者的事后补算。',
            'compare': 'output_only', 'arms': arms(vectors, metadata),
        })
    return results


def main():
    report = json.loads(REPLICATION.read_text())
    history = json.loads(PER_CARD.read_text())['plans']
    historical, private_hashes = historical_cases(history)
    output = {
        'sources': {str(path.relative_to(EXAMPLES)): digest(path) for path in (
            FORMAL_RESULT, PER_CARD, REPLICATION, COMBINED, STAGE / 'src/final_inputs.py',
            STAGE / 'src/final_score.py', STAGE / 'src/final_combined.py', LAB / 'specs/cross-study-v1/formal-v1.json')},
        'checkpoint_provenance': {
            **private_hashes,
            'private_final_pro_log_sha256': digest(WORK / 'final-pro.jsonl'),
            'private_final_people_sha256': digest(WORK / 'people.json'),
        },
        'cases': historical + nhanes_cases(report) + tofu_cases(report),
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
