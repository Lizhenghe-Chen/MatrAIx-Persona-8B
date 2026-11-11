"""Distinguish mean probability concentration from deterministic argmax votes."""
from .population_scoring import distribution_comparison


def summarize(human,synthetic,predictions):
    probabilistic=distribution_comparison(human,synthetic,predictions)
    hard={};ties=0
    for key,probabilities in predictions.items():
        maximum=max(probabilities);ties+=sum(p==maximum for p in probabilities)>1
        selected=probabilities.index(maximum)
        hard[key]=[int(i==selected) for i in range(len(probabilities))]
    deterministic=distribution_comparison(human,synthetic,hard)
    result={'argmax_ties':ties,'thresholds':{},'minimum_people_per_population':20,
            'interpretation':'Both populations must have at least 20 people on a card. Argmax ties use first position; these are descriptive counts, not adoption tests.'}
    supported=[i for i,c in enumerate(probabilistic['cards']) if min(c['human_people'],c['synthetic_people'])>=20]
    result['supported_cards']=len(supported);result['all_cards']=len(probabilistic['cards'])
    for threshold in [.95,.99,1.]:
        result['thresholds'][str(threshold)]={
            'human':sum(max(probabilistic['cards'][i]['human'])>=threshold-1e-12 for i in supported),
            'mean_probabilities':sum(max(probabilistic['cards'][i]['model'])>=threshold-1e-12 for i in supported),
            'argmax_votes':sum(max(deterministic['cards'][i]['model'])>=threshold-1e-12 for i in supported)}
    return result
