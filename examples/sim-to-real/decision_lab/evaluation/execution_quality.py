"""Read-only execution accounting; budgets are not vendor billing statements."""
import sqlite3,json,collections,argparse
from pathlib import Path

def summarize(path):
    path=Path(path);db=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        calls=db.execute('select job,status,reserved_usd,response,error,elapsed from calls').fetchall()
        history=db.execute('select job,error,elapsed from failed_attempts').fetchall() if db.execute("select 1 from sqlite_master where type='table' and name='failed_attempts'").fetchone() else []
    finally:db.close()
    states=collections.Counter(r[1] for r in calls);errors=collections.Counter(r[1] for r in history)
    errors.update(r[4] for r in calls if r[1]=='failed')
    failed_jobs={r[0] for r in history}|{r[0] for r in calls if r[1]=='failed'}
    finished=[r for r in calls if r[1] in ['complete','failed']]
    tokens=collections.Counter();identities=collections.Counter();missing_usage=0
    for _,status,_,response,_,_ in calls:
        if status!='complete':continue
        parsed=json.loads(response);usage=parsed.get('usage',{})
        identities[json.dumps(parsed['identity'],sort_keys=True)]+=1
        if not usage:missing_usage+=1
        for key in ['prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens']:
            if key in usage:tokens[key]+=usage[key]
    return {'database':path.name,'states':dict(states),'jobs_started':len(calls),
            'attempts_including_retries_and_pending':len(calls)+len(history),
            'failed_attempts':sum(errors.values()),'jobs_with_any_failure':len(failed_jobs),
            'first_attempt_failure_fraction_among_finished_jobs':len(failed_jobs & {r[0] for r in finished})/len(finished) if finished else None,
            'error_categories':dict(errors),'successful_response_tokens':dict(tokens),
            'successful_responses_without_usage':missing_usage,
            'identities':[{'identity':json.loads(k),'responses':v} for k,v in identities.items()],
            'reserved_budget_usd':sum(r[2] for r in calls),
            'recorded_request_seconds':sum(r[5] or 0 for r in calls)+sum(r[2] or 0 for r in history),
            'limits':['Token totals omit unsuccessful responses whose usage was not retained.',
                      'Reserved budget is a conservative request bound, not actual invoiced cost.',
                      'A live snapshot is not final completion-rate evidence; compare against frozen expected jobs.',
                      'Legacy ValueError records cannot be retrospectively assigned a more precise cause.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('database',type=Path);a=p.parse_args();print(json.dumps(summarize(a.database),indent=2))
