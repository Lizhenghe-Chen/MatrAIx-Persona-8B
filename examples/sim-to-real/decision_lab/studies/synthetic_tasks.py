"""Preserve observed design exposure by cell without exporting real identities/answers."""
import collections,json,random
from ..core.core import split,digest
from .persona_mapping import common_background


def assign(prepared,cohort,kind,seed=20261109):
    if cohort['source_sha256']!=digest(prepared):raise ValueError('Cohort source mismatch')
    assignments=split(prepared['rows']);by_person=collections.defaultdict(list)
    for r in prepared['rows']:
        if assignments[r['person']]=='test':by_person[r['person']].append(r)
    designs=collections.defaultdict(list)
    for rows in by_person.values():
        bg=common_background(rows[0]['background'],kind)
        if bg is None:continue
        cell=(rows[0]['stratum'],bg['age_bracket'],bg['education_group'])
        designs[cell].append([{'question':r['question'],'context':r['context'],'options':r['options'],'score_group':r.get('score_group',r.get('group'))} for r in sorted(rows,key=lambda r:r['task'])])
    people=collections.defaultdict(list)
    for p in cohort['records']:
        people[(p['stratum'],p['background']['age_bracket'],p['background']['education_group'])].append(p)
    if {k:len(v) for k,v in designs.items()}!={k:len(v) for k,v in people.items()}:raise ValueError('Design exposure counts differ')
    rng=random.Random(seed);tasks=[]
    for cell in sorted(designs):
        rng.shuffle(designs[cell]);synthetic=sorted(people[cell],key=lambda p:p['synthetic_id'])
        for p,questions in zip(synthetic,designs[cell]):
            for i,q in enumerate(questions):
                tasks.append({**q,'synthetic_id':p['synthetic_id'],'task':str(i),'stratum':p['stratum'],
                              'background':p['background'],'generated_personality':p['generated_personality']})
    return {'status':'synthetic_design_no_targets','seed':seed,'cohort_sha256':digest(cohort),
            'prepared_sha256':digest(prepared),'rows':tasks,
            'interpretation':'Within-cell design bundles randomly allocated. No real-person ID, answer, or individual accuracy target.'}
