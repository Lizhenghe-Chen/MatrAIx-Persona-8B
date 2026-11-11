"""Matched background diagnostics and reversible option permutations."""
import copy
import random
from collections import defaultdict
from .core import digest, probabilities


def shuffled_background(rows, basic_fields, additional_fields, assignments, seed=20261109):
    """Derange whole blocks within design stratum, basic background and split.

    Singleton cells remain unchanged and are flagged, never described as shuffled.
    Donor map is local-only. Nothing is inferred or generated.
    """
    if set(basic_fields)&set(additional_fields):raise ValueError('Overlapping field blocks')
    persons={};groups=defaultdict(list)
    for row in rows:
        person=row['person']; signature=(row['stratum'],row['background'])
        if person in persons and persons[person]!=signature:
            raise ValueError('Background varies within person')
        persons[person]=signature
    for person,(stratum,background) in sorted(persons.items()):
        key=digest([assignments[person],stratum,{f:background.get(f,'unknown') for f in basic_fields}])
        groups[key].append(person)
    rng=random.Random(seed);donors={};unchanged=[]
    for key,people in sorted(groups.items()):
        rng.shuffle(people)
        if len(people)==1:unchanged.extend(people)
        for i,person in enumerate(people):donors[person]=people[(i+1)%len(people)]
    result=copy.deepcopy(rows)
    for row in result:
        donor=persons[donors[row['person']]][1]
        for field in additional_fields:row['background'][field]=donor.get(field,'unknown')
    content_changed=[person for person in persons if any(
        persons[person][1].get(field,'unknown') != persons[donors[person]][1].get(field,'unknown')
        for field in additional_fields)]
    return result,{'donors':donors,'unshuffled_singletons':unchanged,
                   'content_changed_people':content_changed,
                   'people':len(persons),'shuffled_people':len(persons)-len(unchanged)}


def permute_options(row, order):
    n=len(row['options'])
    if sorted(order)!=list(range(n)):raise ValueError('Invalid permutation')
    result=copy.deepcopy(row)
    result['options']=[row['options'][i] for i in order]
    result['answer']=order.index(row['answer'])
    return result


def restore_probabilities(values, order):
    probabilities(values,len(order))
    if sorted(order)!=list(range(len(order))):raise ValueError('Invalid permutation')
    original=[0.]*len(order)
    for displayed,source in enumerate(order):original[source]=values[displayed]
    return original
