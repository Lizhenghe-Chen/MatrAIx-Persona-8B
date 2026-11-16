"""Borrow Qwen attribute preferences through a fixed pseudo-choice likelihood."""
import json

from adaptive_pilot import spanish
import optout_pilot as pilot


if __name__ == '__main__':
    inputs = {**pilot.load(), 'spain':spanish()}
    print(json.dumps({'seed':pilot.SEED,'splits':pilot.REPEATS,'new_calls':0,
                      'pseudo_choice_mass':pilot.PSEUDO_CHOICE_MASS,
                      'studies':{name:pilot.evaluate(*args,attribute_prior=True)
                                 for name,args in inputs.items()}},indent=2))
