"""Swiss six-category study: verified item wording, person linkage and task extraction.

Wording comes from the authors' supplementary A.1; survey order from A.10 (full
questionnaire screenshots). Both were read locally; the item-to-construct mapping is
checked against the paper's Table 2 reliabilities by `admission.py`.

No answer-derived field may be exposed to a model. Phone/rating columns stay local.
"""
import json
from collections import defaultdict
from pathlib import Path

DATA_ROOT = Path.home() / '.local/share/matraix-decision-transfer'
RAW = Path('/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据/02_瑞士六品类')

# (column, block, verbatim wording). Table A.1/A.2 order is verified against the
# author R labels and against the reproduced reliabilities, not assumed from column order.
TPB_ITEMS = [
    ('w14_q29x1', 'attitude', 'For me, buying environmentally friendly PRODUCTS is a good idea.'),
    ('w14_q29x2', 'attitude', 'For me, purchasing environmentally friendly PRODUCTS is pleasant.'),
    ('w14_q29x3', 'attitude', 'For me, purchasing environmentally friendly PRODUCTS is a wise choice.'),
    ('w14_q29x10', 'norm', 'Most people who are important to me think I should buy environmentally friendly PRODUCTS.'),
    ('w14_q29x11', 'norm', 'Most people whose opinions I value prefer that I buy environmentally friendly PRODUCTS.'),
    ('w14_q29x12', 'norm', 'It is important to me to do what people who are important to me and whose opinions I value think I should do.'),
    ('w14_q29x5', 'control', 'I am confident that, if I want, I can buy environmentally friendly PRODUCTS.'),
]
DIPB_ITEMS = [
    ('w14_q30x1', 'change', "There's not much point in me making such changes because I feel confident that technological innovators will solve environmental problems."),
    ('w14_q30x2', 'change', 'Humans are powerless when it comes to saving the Earth, so there is no point for me to change.'),
    ('w14_q30x3', 'change', 'Environmental problems are far in the future, so there is no need to act.'),
    ('w14_q30x4', 'change', 'Such changes are not really necessary for me because environmental conditions are likely to remain ok in my area.'),
    ('w14_q30x5', 'change', 'There is no pressing need to change because nature has great resiliency and our actions are trivial.'),
    ('w14_q30x6', 'goals', 'Making such changes would interfere too much with my other goals in life.'),
    ('w14_q30x7', 'goals', "I'm concerned that such changes will take up too much of my time."),
    ('w14_q30x8', 'goals', "I can't change because I'm invested in my current lifestyle."),
    ('w14_q30x9', 'goals', "Environmental concerns are important to me but it's too hard to change my habits."),
    ('w14_q30x10', 'goals', "I haven't changed because I'm afraid this wouldn't work."),
    ('w14_q30x11', 'relations', 'Making such changes would be criticized by those around me.'),
    ('w14_q30x12', 'relations', 'I would be letting certain people down if I made such changes.'),
    ('w14_q30x13', 'relations', "I'm worried that my friends would disapprove if I made such changes."),
    ('w14_q30x14', 'relations', 'If I made the necessary changes, I probably would be embarrassed when others noticed what I was doing.'),
    ('w14_q30x15', 'knowledge', "There's so much information out there that I'm confused about how to make such changes."),
    ('w14_q30x16', 'knowledge', "I don't understand enough of the details about how to make such changes."),
    ('w14_q30x17', 'knowledge', "I'd like to change, but I'm not sure where to begin."),
    ('w14_q30x18', 'knowledge', 'The pro-environmental efforts that I currently engage in make further changes unnecessary.'),
    ('w14_q30x19', 'token', 'I have already made sacrifices to solve environmental problems, so there is no need for me to do more.'),
    ('w14_q30x20', 'token', 'I previously have made important efforts in this, so there is no need for me to make further changes.'),
    ('w14_q30x21', 'token', 'My environmental actions already make enough of a difference.'),
    ('w14_q30x22', 'token', "It's not fair for me to change when really it's industry that's causing the majority of environmental problems."),
]
FACT_ITEMS = TPB_ITEMS + DIPB_ITEMS
PROHIBITED = ['choice', 'rating', 'rating_num', 'green_grmscore_rescaled', 'green_idealscore_rescaled',
              'green_coefscore_rescaled', 'intention_tpb', 'w14_q29x7', 'w14_q29x8', 'w14_q29x9']
PRODUCT_DOMAIN = {'Laptop': 'electronics', 'Smartphone': 'electronics', 'Jacket': 'clothes',
                  'Shirt': 'clothes', 'Tomatoes (1kg)': 'food', 'Chocolate (100g)': 'food'}
SCALE = {'attitude': ('does not apply at all', 'fully applies'),
         'norm': ('does not apply at all', 'fully applies'),
         'control': ('does not apply at all', 'fully applies'),
         'dipb': ('strongly disagree', 'strongly agree')}
# Paper Table 2: construct -> (alpha, mean, sd).
PAPER_TABLE2 = {'attitude': (0.89, 5.54, 1.38), 'norm': (0.76, 3.79, 1.55), 'intention': (0.91, 5.37, 1.44),
                'change': (0.83, 1.98, 1.06), 'goals': (0.80, 2.25, 1.03), 'relations': (0.83, 1.64, 0.91),
                'knowledge': (0.68, 2.70, 1.13), 'token': (0.72, 2.70, 1.18)}
BLOCKS = {b: [c for c, blk, _ in FACT_ITEMS if blk == b] for b in dict.fromkeys(blk for _, blk, _ in FACT_ITEMS)}
BLOCKS['intention'] = ['w14_q29x7', 'w14_q29x8', 'w14_q29x9']  # excluded from model input, kept for checks


def _sanitize(values):
    import numpy as np
    array = np.asarray(values)
    if isinstance(array, np.ma.MaskedArray):
        array = np.asarray(array.filled(np.nan))
    if array.ndim == 2 and array.shape[1] == 1:
        array = array[:, 0]
    array = np.asarray(array)
    if array.ndim != 1:
        array = array.reshape(-1)
    if array.dtype == object:
        array = np.array([x[0] if isinstance(x, (list, tuple, np.ndarray)) and len(x) == 1 else x for x in array],
                         dtype=object)
    return array


def load_sep(path=RAW / 'SEP_w14_reduced.RData'):
    """pyreadr cannot build this frame (some columns are stored as n-by-1 matrices)."""
    import pandas as pd
    import rdata
    from rdata.conversion import convert
    from rdata.conversion._conversion import default_class_map_dict

    def patched(obj, attrs):
        return pd.DataFrame({k: _sanitize(v) for k, v in obj.items()})

    class_map = dict(default_class_map_dict)
    class_map['data.frame'] = patched
    return convert(rdata.parser.parse_file(str(path)), class_map)['data']


def load_conjoint(path=RAW / 'w14_conjoint.RData'):
    import pyreadr
    return pyreadr.read_r(str(path))['dfconj']


def _person_level(conjoint):
    frame = conjoint[conjoint['PubId'].notna()]
    return frame.drop_duplicates('PubId').sort_values('PubId').reset_index(drop=True)


def link(sep, conjoint):
    """SEP rows are in PubId order: verified by exact reproduction of eight aggregates."""
    import numpy as np
    import pandas as pd
    persons = _person_level(conjoint)
    n = min(len(sep), len(persons))
    checks = {}
    for block, cols in BLOCKS.items():
        if block == 'control':
            continue
        target = {'attitude': 'attitude_tpb', 'norm': 'norm_tpb', 'intention': 'intention_tpb',
                  'change': 'change_di', 'goals': 'goal_di', 'relations': 'relations_di',
                  'knowledge': 'know_di', 'token': 'token_di'}[block]
        computed = sep[cols].mean(axis=1).to_numpy()[:n]
        stored = pd.to_numeric(persons[target], errors='coerce').to_numpy()[:n]
        both = ~np.isnan(computed) & ~np.isnan(stored)
        exact = int((np.abs(computed[both] - stored[both]) < 1e-6).sum())
        checks[target] = {'compared': int(both.sum()), 'exact': exact}
    if any(v['compared'] < 5000 or v['exact'] != v['compared'] for v in checks.values()):
        raise ValueError('Person linkage not reproduced: ' + json.dumps(checks))
    return persons, checks


def alpha(frame):
    d = frame.dropna()
    k = d.shape[1]
    if k < 2 or len(d) < 10:
        return None
    return float(k / (k - 1) * (1 - d.var(ddof=1).sum() / d.sum(axis=1).var(ddof=1)))


def reliability(sep):
    """Recompute Table 2; a mismatch would mean the item-to-construct map is wrong."""
    out = {}
    for block, cols in BLOCKS.items():
        frame = sep[cols]
        d = frame.dropna()
        a = alpha(frame)
        out[block] = {'alpha': round(a, 3) if a else None,
                      'mean': round(float(d.mean().mean()), 2) if len(d) else None,
                      'sd': round(float(d.mean(axis=1).std(ddof=1)), 2) if len(d) else None}
    return out


def check_reliability(reliability_rows, tolerance=(0.02, 0.12, 0.06)):
    bad = []
    for block, paper in PAPER_TABLE2.items():
        calc = reliability_rows[block]
        if calc['alpha'] is None:
            bad.append((block, 'missing'))
            continue
        if abs(calc['alpha'] - paper[0]) > tolerance[0] or abs(calc['mean'] - paper[1]) > tolerance[1] \
                or abs(calc['sd'] - paper[2]) > tolerance[2]:
            bad.append((block, calc, paper))
    return bad


def people(sep, conjoint):
    """Person rows: demographics, facts (1-7 or None) and the two assigned products."""
    persons, checks = link(sep, conjoint)
    tasks = defaultdict(list)
    for row in conjoint.itertuples(index=False):
        if not isinstance(row.product, str) or row.product not in PRODUCT_DOMAIN:
            continue
        if row.choice is None or row.choice != row.choice or row.round != row.round:
            continue
        tasks[row.PubId].append({'product': row.product, 'domain': PRODUCT_DOMAIN[row.product],
                                 'round': int(row.round), 'offer': int(row.measure),
                                 'price': row.price, 'impact': row.impact, 'chosen': int(row.choice)})
    out = []
    for index, row in persons.iterrows():
        pub = int(row['PubId'])
        items = tasks.get(pub, [])
        if index >= len(sep):
            continue
        sep_row = sep.iloc[index]
        facts = {}
        for column, block, _ in FACT_ITEMS:
            value = sep_row[column]
            facts[column] = None if value is None or (isinstance(value, float) and value != value) else int(value)
        out.append({'pub_id': pub, 'facts': facts, 'tasks': items,
                    'background': {'age_years': _num(row.get('age_num')),
                                   'age_band': _text(row.get('age')),
                                   'education': _text(row.get('educ')),
                                   'gender': _text(row.get('gender')),
                                   'income_band': _text(row.get('inc')),
                                   'country': 'Switzerland'}})
    return out, checks, len(persons)


def _num(value):
    try:
        if value is None or value != value:
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _text(value):
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ('', 'nan', 'NA') else text


def valid_task_person(person):
    """Exactly two products, three paired rounds each, one choice per round."""
    by_product = defaultdict(list)
    for item in person['tasks']:
        by_product[item['product']].append(item)
    if len(by_product) != 2:
        return False
    for rows in by_product.values():
        rounds = defaultdict(list)
        for item in rows:
            rounds[item['round']].append(item)
        if len(rounds) != 3:
            return False
        for items in rounds.values():
            if sorted(i['offer'] for i in items) != [1, 2] or sum(i['chosen'] for i in items) != 1:
                return False
    return True


def facts_text(facts, prefix='- '):
    """Render the 29 verified items; missing answers stay explicitly unknown."""
    lines = []
    for column, block, wording in FACT_ITEMS:
        low, high = SCALE['dipb'] if block not in ('attitude', 'norm', 'control') else SCALE[block]
        value = facts.get(column)
        answer = 'Unknown (no answer given)' if value is None else f'{value} on a 1-7 scale ({low} ... {high})'
        lines.append(f'{prefix}"{wording}" -> {answer}')
    return '\n'.join(lines)


def domain_of(person):
    domains = {item['domain'] for item in person['tasks']}
    return domains.pop() if len(domains) == 1 else None
