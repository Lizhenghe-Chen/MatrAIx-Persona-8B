"""Stage-2 sampling and donor assignment for the Swiss study.

Allocations follow the original stratum population by largest remainder; selection and
donor order come from a fixed seed, never from any answer. Reserved categories stay
untouched so a later new-category check is not contaminated.
"""
import hashlib
from collections import Counter, defaultdict

import swiss

SEED = 20261109
STAGE2_DOMAIN = 'electronics'
RESERVE = {'clothes': 48, 'food': 48}
EVAL, TECH = 48, 4


def cell_of(person):
    background = person['background']
    return (background['age_band'], background['education'])


def cage_of(person):
    background = person['background']
    return (background['age_band'], background['education'], background['gender'])


def eligible(person, domain):
    return (swiss.domain_of(person) == domain and swiss.valid_task_person(person)
            and all(value is not None for value in person['facts'].values())
            and person['background']['age_band'] and person['background']['education']
            and person['background']['gender'])


def largest_remainder(counts, total):
    """Allocate `total` seats in proportion to counts; ties broken by cell name."""
    population = sum(counts.values())
    if population == 0:
        return {}
    total = min(total, population)
    quota = {cell: total * n / population for cell, n in counts.items()}
    seats = {cell: int(value) for cell, value in quota.items()}
    for cell in sorted(counts, key=lambda c: (-(quota[c] - seats[c]), c))[:total - sum(seats.values())]:
        seats[cell] += 1
    return seats


def _rank(tag, cell, pub_id):
    return hashlib.sha256(f'{SEED}:{tag}:{cell}:{pub_id}'.encode()).hexdigest()


def pick(by_cell, seats, tag):
    chosen = []
    for cell, count in sorted(seats.items()):
        if count <= 0:
            continue
        ranked = sorted(by_cell.get(cell, []), key=lambda p: _rank(tag, cell, p['pub_id']))
        chosen.extend(ranked[:count])
    return chosen


def donor_for(recipient, by_cage, by_cell, blocked):
    """Same category domain and coarse age/education cell; same gender preferred."""
    for key, pool in ((cage_of(recipient), by_cage), (cell_of(recipient), by_cell)):
        candidates = [p for p in pool.get(key, []) if p['pub_id'] not in blocked]
        if candidates:
            candidates.sort(key=lambda p: hashlib.sha256(
                f'{SEED}:donor:{recipient["pub_id"]}:{p["pub_id"]}'.encode()).hexdigest())
            return candidates[0]
    return None


def _index(people):
    by_cell, by_cage = defaultdict(list), defaultdict(list)
    for person in people:
        by_cell[cell_of(person)].append(person)
        by_cage[cage_of(person)].append(person)
    return by_cell, by_cage


def build(sep, conjoint):
    people, linkage, persons_total = swiss.people(sep, conjoint)
    by_domain = defaultdict(list)
    for person in people:
        by_domain[swiss.domain_of(person)].append(person)

    stage2 = [p for p in by_domain[STAGE2_DOMAIN] if eligible(p, STAGE2_DOMAIN)]
    by_cell, by_cage = _index(stage2)
    counts = {cell: len(rows) for cell, rows in by_cell.items()}

    reserved, used = {}, set()
    for domain, size in RESERVE.items():
        pool = [p for p in by_domain[domain] if eligible(p, domain)]
        domain_cell, _ = _index(pool)
        picked = pick(domain_cell, largest_remainder({c: len(r) for c, r in domain_cell.items()}, size),
                      f'reserve:{domain}')
        reserved[domain] = picked
        used.update(p['pub_id'] for p in picked)

    available = {cell: [p for p in rows if p['pub_id'] not in used] for cell, rows in by_cell.items()}
    evaluation = pick(available, largest_remainder({c: len(r) for c, r in available.items()}, EVAL), 'evaluation')
    taken = used | {p['pub_id'] for p in evaluation}

    technical = pick({c: [p for p in rows if p['pub_id'] not in taken] for c, rows in by_cell.items()},
                     largest_remainder(counts, TECH), 'technical')

    blocked = taken | {p['pub_id'] for p in technical}
    donors, missing = {}, []
    for recipient in evaluation + technical:
        donor = donor_for(recipient, by_cage, by_cell, blocked)
        if donor is None:
            missing.append(recipient['pub_id'])
            continue
        donors[recipient['pub_id']] = donor['pub_id']
        blocked.add(donor['pub_id'])

    return {'people': people, 'linkage': linkage, 'persons_total': persons_total,
            'eligible_stage2': stage2, 'evaluation': evaluation, 'technical': technical,
            'reserved': reserved, 'donors': donors, 'donors_missing': missing, 'cells': counts}


def summarise(result):
    """Public summary: counts only, no identifiers or answers."""
    return {
        'seed': SEED,
        'domain': STAGE2_DOMAIN,
        'persons_with_choices': result['persons_total'],
        'eligible_stage2': len(result['eligible_stage2']),
        'evaluation': len(result['evaluation']),
        'technical': len(result['technical']),
        'reserved': {domain: len(rows) for domain, rows in result['reserved'].items()},
        'donors_assigned': len(result['donors']),
        'donors_missing': len(result['donors_missing']),
        'strata': {' | '.join(cell): n for cell, n in sorted(result['cells'].items())},
        'evaluation_by_stratum': {' | '.join(c): n for c, n in
                                  sorted(Counter(cell_of(p) for p in result['evaluation']).items())},
        'technical_by_stratum': {' | '.join(c): n for c, n in
                                 sorted(Counter(cell_of(p) for p in result['technical']).items())},
        'linkage_checks': result['linkage'],
        'notes': [
            'Evaluation and technical participants are disjoint; reserved categories are frozen and never reused.',
            'A donor shares the study, category domain and coarse age/education cell, prefers the same gender, '
            'is never the recipient, and is used once.',
            'Eligibility requires two products with three paired rounds each, one choice per round, all 29 '
            'fact items answered and all four background labels present.',
        ],
    }
