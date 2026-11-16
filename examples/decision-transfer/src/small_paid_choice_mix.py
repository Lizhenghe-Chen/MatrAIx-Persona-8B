"""Evaluate fixed model blending under constrained hypothetical-survey budgets."""
import json

from paid_choice_model_mix import REPLAYS, SEED, WEIGHT, beef_inputs, evaluate, orange_inputs

BUDGETS = (5, 10, 25, None)


def main():
    orange_x, *orange_data = orange_inputs()
    # fit_products restricts the last feature, so price must follow carbon.
    studies = {'orange': (orange_x[..., ::-1], *orange_data), 'beef': beef_inputs()}
    results = {
        name: {budget if budget is not None else 'all': evaluate(*inputs, source_budget=budget)
               for budget in BUDGETS}
        for name, inputs in studies.items()
    }
    print(json.dumps({'seed': SEED, 'replays': REPLAYS, 'new_calls': 0, 'qwen_weight': WEIGHT,
                      'studies': results}, indent=2))


if __name__ == '__main__':
    main()
