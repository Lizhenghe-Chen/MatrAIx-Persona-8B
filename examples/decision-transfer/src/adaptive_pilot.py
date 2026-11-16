"""Re-score three historical studies with a pilot-only cross-fitted blend."""
import json

import numpy as np

import optout_pilot as pilot
import optout_transfer
import radiant_pilot


def spanish():
    frame, jobs, features = radiant_pilot.deck()
    prediction, identities = optout_transfer.predictions(jobs, radiant_pilot.RUN)
    if len(identities)!=1:
        raise ValueError('Mixed model versions')
    people = []
    for _, rows in frame.groupby('unique_id'):
        chosen = rows[rows.choice==1].sort_values('choice_card')
        if len(chosen)!=6 or chosen.choice_card.nunique()!=6:
            raise ValueError('Invalid choice card answers')
        people.append({f'card{r.choice_card:02}':str(r.option if r.option!=3 else 0)
                       for r in chosen.itertuples(index=False)})
    p, y = optout_transfer.outcome(prediction, people)
    keys = np.asarray([list(row) for row in people])
    x = np.asarray([[features[k] for k in row] for row in keys])
    return p, y, keys, None, x


if __name__ == '__main__':
    inputs = {**pilot.load(), 'spain':spanish()}
    print(json.dumps({'seed':pilot.SEED,'splits':pilot.REPEATS,'new_calls':0,
                      'studies':{name:pilot.evaluate(*args,adaptive=True)
                                 for name,args in inputs.items()}},indent=2))
