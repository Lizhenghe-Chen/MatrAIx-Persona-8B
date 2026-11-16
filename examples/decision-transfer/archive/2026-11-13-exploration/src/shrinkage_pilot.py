"""Assess probability shrinkage towards uniform choices on four historical studies."""
import json

from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
import optout_pilot as pilot


if __name__ == '__main__':
    italian, _, _ = evaluation_inputs(*load_deck())
    datasets = {**pilot.load(), 'spain': spanish(), 'italy': italian}
    output = {'seed': pilot.SEED, 'splits': pilot.REPEATS, 'new_calls': 0, 'studies': {}}
    for study, inputs in datasets.items():
        output['studies'][study] = pilot.evaluate(*inputs, shrinkage=True)
    print(json.dumps(output, indent=2))
