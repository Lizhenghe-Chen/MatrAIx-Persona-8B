"""Cluster-level summary across every study that has been run.

Studies inside one dataset/panel are not independent replications, so counts are
reported both ways: number of studies and number of independent clusters. Only the
metric every study shares is pooled - improvement over "every option equally likely" -
because the strength of the same-information reference differs by study.
"""
import json

from .registry import OUT

RESULTS = {'v1': 'formal-results.json', 'clean-v1': 'clean-v1-results.json',
           'wide-v1': 'wide-v1-results.json'}
CLUSTERS = {'shed': 'Pew', 'pew168': 'Pew', 'pew13': 'Pew', 'pew111': 'Pew',
            'anes': 'ANES', 'swiss': 'Swiss panel', 'dryer': 'Dryer (4 countries)',
            'origin': 'Origin', 'packaging': 'Packaging', 'shoes': 'Shoes', 'drone': 'Drone',
            'german': 'German tomato', 'tshirt': 'T-shirt', 'radiant': 'Spanish tomato'}
REFERENCE_ORDER = ('stratum_history__to__optimized', 'history__to__optimized',
                   'attribute_logit__to__optimized', 'attribute_rating__to__optimized')


def _available(contrast):
    return bool(contrast) and contrast.get('available', True)


def collect():
    rows = []
    for plan, name in RESULTS.items():
        path = OUT / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for study, entry in data['studies'].items():
            arms = entry['results']['arms']
            uniform = arms['uniform']['brier']
            if not uniform or arms['optimized']['brier'] is None:
                continue
            key = next((k for k in REFERENCE_ORDER
                        if _available(entry['results']['contrasts'].get(k))), None)
            contrast = entry['results']['contrasts'].get(key) if key else None
            rows.append({
                'plan': plan, 'study': study, 'cluster': CLUSTERS.get(study, study),
                'people': entry['people'],
                'ai_over_uniform': round(1 - arms['optimized']['brier'] / uniform, 4),
                'reference': None if key is None else key.split('__to__')[0],
                'reference_over_uniform': (
                    None if key is None else
                    round(1 - arms[key.split('__to__')[0]]['brier'] / uniform, 4)),
                'ai_vs_reference': (None if contrast is None else
                                    round(contrast['relative_improvement'], 4)),
                'ai_vs_reference_ci': (None if contrast is None else
                                       [round(v, 4) for v in contrast['improvement_95_ci']]),
                'cards_estimable': entry.get('cards_with_at_least_20_people'),
                'cards': entry.get('cards'),
            })
    return rows


def summarise(rows):
    with_reference = [r for r in rows if r['ai_vs_reference'] is not None]
    behind = [r for r in with_reference if r['ai_vs_reference'] < 0]
    clusters = sorted({r['cluster'] for r in rows})
    behind_clusters = sorted({r['cluster'] for r in behind})
    return {
        'studies': len(rows),
        'studies_with_reference': len(with_reference),
        'clusters': len(clusters),
        'cluster_names': clusters,
        'studies_behind_reference': len(behind),
        'clusters_behind_reference': len(behind_clusters),
        'any_ci_above_zero': [r['study'] for r in with_reference
                              if r['ai_vs_reference_ci'][1] > 0],
        'mean_ai_over_uniform': round(sum(r['ai_over_uniform'] for r in rows) / len(rows), 4),
        'mean_reference_over_uniform': round(
            sum(r['reference_over_uniform'] for r in with_reference) / len(with_reference), 4),
        'population_estimable_studies': [r['study'] for r in rows
                                         if (r['cards_estimable'] or 0) > 0],
        'note': ('Studies sharing a dataset or panel are one cluster. Pooling only uses the '
                 'improvement over "every option equally likely", the one metric every study has; '
                 'reference strength differs and is never averaged across studies.'),
    }


def main():
    rows = collect()
    report = {'rows': rows, 'summary': summarise(rows)}
    (OUT / 'cluster-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
