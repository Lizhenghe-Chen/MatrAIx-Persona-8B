"""Evaluate frozen 75/25 price/Qwen blending in pepper and dryer surveys."""
import json
import re

import numpy as np

import dryer_refusal_transfer as dryers
from optout_transfer import outcome, predictions
from small_choice_mix_transfer import REPEATS, SEED, WEIGHT, evaluate
import taiwan_pepper as pepper


def data(deck, people, features, directory, *, refusal_last=False):
    predicted, identities = predictions(deck, directory)
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    p, y = outcome(predicted, people)
    if refusal_last:
        p, y = (np.roll(a, 1, axis=-1) for a in (p, y))
    keys = np.asarray([list(person) for person in people])
    x = np.asarray([[features[k] for k in row] for row in keys])
    return p, y, keys, x


def pepper_features(label):
    origin = re.search(r'產地：([^；]+)', label)[1]
    return [float(origin == '台灣'), float(origin == '日本'), float('有機生產' in label),
            float('通過台灣的農藥殘留檢測' in label),
            float('農藥殘留檢測' in label and '通過台灣的農藥殘留檢測' not in label),
            (int(re.search(r'NT (\d+)', label)[1]) - 95) / 20]


def main():
    deck = pepper.deck()
    features = {key: [pepper_features(job['questions'][0]['options'][i]) for i in ('1', '2', '3')]
                for key, job in deck.items()}
    inputs = {'taiwan': data(deck, pepper.observed_control(deck), features, pepper.RUN, refusal_last=True)}
    deck, features, countries = dryers.load()
    for country, people in countries.items():
        local = {key: job for key, job in deck.items() if key.startswith(f'{country}-')}
        rows = [dict(sorted(row.items())) for row in people.values()]
        inputs[country] = data(local, rows, features, dryers.RUN)
    print(json.dumps({'seed': SEED, 'replays': REPEATS, 'qwen_weight': WEIGHT, 'new_calls': 0,
                      'studies': {key: evaluate(*args, price_uniform_control=True)
                                  for key, args in inputs.items()}}, indent=2))


if __name__ == '__main__':
    main()
