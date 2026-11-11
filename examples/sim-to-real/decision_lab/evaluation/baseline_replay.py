"""Replay frozen coefficients without fitting or selecting on evaluation answers."""
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from ..core.core import digest,split
from ..core.baselines import ConditionalLogit


def replay(prepared,saved,rows,kind,arm):
    if saved['source_sha256']!=digest(prepared):raise ValueError('Baseline source mismatch')
    if kind=='dryer':from ..studies.dryer_baseline import tasks
    elif kind=='swiss':from ..studies.swiss_baseline import tasks
    else:raise ValueError('Unknown reviewed adapter')
    assignment=split(prepared['rows'])
    if any(assignment.get(r['person']) not in ('development','test') for r in rows):
        raise ValueError('Replay requires held-out people')
    # Verify full rows, not just identities: background/answer changes are not hidden.
    original={(r['person'],r['task']):r for r in prepared['rows']}
    if any(original.get((r['person'],r['task']))!=r for r in rows):
        raise ValueError('Evaluation row differs from frozen source')
    train=[r for r in prepared['rows'] if assignment[r['person']]=='train']
    params=saved['baselines'][arm];vectorizer=DictVectorizer(sparse=False)
    tasks(train,params['background_fields'],vectorizer,True)
    if vectorizer.get_feature_names_out().tolist()!=params['background_feature_names']:
        raise ValueError('Feature vocabulary changed')
    model=ConditionalLogit(params['penalty'])
    model.beta=np.asarray(params['beta']);model.scale=np.asarray(params['scale'])
    if model.beta.ndim!=1 or model.scale.shape!=model.beta.shape or not np.isfinite(model.beta).all() or not np.isfinite(model.scale).all() or np.any(model.scale<=0):
        raise ValueError('Invalid saved coefficients or scale')
    predictions=model.predict(tasks(rows,params['background_fields'],vectorizer))
    return {(r['person'],r['task']):p for r,p in zip(rows,predictions)}
