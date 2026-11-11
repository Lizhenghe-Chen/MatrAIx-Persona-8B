"""Summarize frozen study contrasts without inventing pooled uncertainty."""

CONTRASTS={
 'none__to__basic':'补充年龄与学历',
 'basic__to__rich':'增加贴题真实背景',
 'statistics_rich__to__rich':'纯 AI 是否超过同背景统计模型',
 'rich__to__calibrated':'开发阶段选定方案是否超过纯 AI',
 'statistics_rich__to__calibrated':'开发阶段选定方案是否超过同背景统计模型',
}


def summarize(studies):
    if not studies:raise ValueError('No completed studies')
    if any(s.get('status')!='complete_test_primary_brier_only' for s in studies):raise ValueError('Incomplete test evidence')
    kinds=[s['kind'] for s in studies]
    if len(set(kinds))!=len(kinds):raise ValueError('Duplicate study; countries or reruns must not count as independent studies')
    output={}
    for contrast,label in CONTRASTS.items():
        results=[]
        for study in studies:
            if contrast not in study['comparisons']:raise ValueError('Missing prespecified comparison')
            c=study['comparisons'][contrast];lo,hi=c['improvement_95_ci']
            results.append({'study':study['kind'],'relative_improvement':c['relative_improvement'],
                            'absolute_improvement':c['improvement'],'improvement_95_ci':[lo,hi],
                            'passes':c['passes_2_percent_gate'],'clear_regression':hi<0,
                            'selected_llm_weight':study['calibration_llm_weight']})
        passed=sum(r['passes'] for r in results);regressed=sum(r['clear_regression'] for r in results)
        output[contrast]={'label':label,'studies':results,'passing_studies':passed,'clearly_regressing_studies':regressed,
                          'replicated_within_included_studies':passed>=2 and regressed==0,
                          'broad_cross_study_claim_allowed':False,
                          'scope':'Current admitted studies are appliance choices only; no cross-industry claim. No pooled confidence interval computed from per-study intervals.'}
    return {'status':'complete_comparison_summary','independent_studies':len(studies),'contrasts':output,
            'limits':['A selected LLM weight of zero is a statistical prediction, not an improvement of the LLM.',
                      'No single overall Brier score mixes different option counts.',
                      'This summary concerns measured-background individual prediction; generated populations must be reported separately.']}

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('analyses',nargs='+',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=summarize([json.loads(p.read_text()) for p in args.analyses])
    with args.output.open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
