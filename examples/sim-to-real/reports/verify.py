"""Verify the reader report without API requests or private respondent exports."""
from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build import HERE, PRIVATE, validate


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.resources = [], set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, attrs['id']
            self.ids.add(attrs['id'])
        if 'href' in attrs:
            self.links.append(attrs['href'])
        if 'src' in attrs:
            self.resources.append(attrs['src'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-sources',action='store_true')
    args=parser.parse_args()
    data=json.loads((HERE/'evidence.json').read_text())
    validate(data)
    checked=0
    for source in data['sources']:
        if source['storage']=='local_only':
            if not args.local_sources:
                continue
            path=PRIVATE / source['path'].removeprefix('local-analysis/')
        else:
            path=HERE / source['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256'],path
        checked+=1
    html=(HERE/'index.html').read_text()
    doc=Links();doc.feed(html)
    for href in doc.links:
        url=urlsplit(href)
        if url.scheme: continue
        if url.path:
            assert (HERE/unquote(url.path)).exists(),href
        elif url.fragment:
            assert unquote(url.fragment) in doc.ids,href
    assert not doc.resources, 'Report must be self-contained'
    assert all(label not in html for label in ('P0+B1','P1+B3','p0-b1','p1-b3'))
    # Tie headline/average table claims to exact, unrounded stored values.
    for name,label in [('只选一项','43.41'),('保留概率','18.08'),('真人数据校准','5.43'),('真人统计模型','4.59')]:
        average=sum(q['methods'][name]['error'] for q in data['questions'])/13
        assert f'{average:.2f}'==label,(name,average)
    for key,value in [('qwen/matched','15.95'),('pro/matched','11.50')]:
        assert f"{data['matching']['summary'][key]['mean_run_tv_pp']:.2f}"==value
    assert data['history']['execution']['attempts']==600
    assert data['history']['aborted_run']['attempts']==419
    assert data['history']['aborted_run']['scores_computed'] is False
    assert data['history']['recommend_independent_replication'] is False
    cross=HERE.parent/'decision_lab/reports/cross-study-v1/formal-report.summary.json'
    if cross.exists():
        summary=json.loads(cross.read_text())
        html_cross=(HERE/'index.html').read_text()
        assert 'id="cross-study"' in html_cross
        for key in summary['rows']:
            assert f'{100*summary["rows"][key]["brier"]["relative_improvement"]:+.1f}%' in html_cross, key
        assert (HERE.parent/'decision_lab/reports/cross-study-v1/formal-report.html').exists()
        assert (HERE.parent/'decision_lab/docs/推荐配置.md').exists()
        cross_note=f' cross-study summary for {len(summary["rows"])} studies tied to the generated page;'
    else:
        cross_note=''
    clean=HERE.parent/'decision_lab/reports/cross-study-v1/clean-v1-report.summary.json'
    cluster=HERE.parent/'decision_lab/reports/cross-study-v1/cluster-summary.json'
    cluster_note=''
    if cluster.exists():
        data=json.loads(cluster.read_text())
        html_all=(HERE/'index.html').read_text()
        assert 'id="all-studies"' in html_all
        for row in data['rows']:
            assert f'{100*row["ai_over_uniform"]:+.1f}%' in html_all, row['study']
        stats=data['summary']
        assert f'+{100*stats["mean_ai_over_uniform"]:.1f}%' in html_all
        assert f'{stats["studies_behind_reference"]}/{stats["studies"]}' in html_all
        cluster_note=f' cluster summary for {stats["studies"]} studies / {stats["clusters"]} clusters tied to the page;'
    wide=HERE.parent/'decision_lab/reports/cross-study-v1/wide-v1-results.json'
    wide_note=''
    if wide.exists():
        wide_data=json.loads(wide.read_text())
        html_wide=(HERE/'index.html').read_text()
        assert 'id="wide"' in html_wide
        for study,entry in wide_data['studies'].items():
            arms=entry['results']['arms']
            versus=(arms['uniform']['brier']-arms['optimized']['brier'])/arms['uniform']['brier']
            assert f'{100*versus:+.1f}%' in html_wide, study
        wide_note=f' wide summary for {len(wide_data["studies"])} studies tied to the generated page;'
    clean_note=''
    if clean.exists():
        clean_summary=json.loads(clean.read_text())
        clean_results=json.loads((clean.parent/'clean-v1-results.json').read_text())
        html_clean=(HERE/'index.html').read_text()
        assert 'id="clean-v1"' in html_clean
        for key,row in clean_summary['rows'].items():
            assert f'{100*row["brier"]["relative_improvement"]:+.1f}%' in html_clean, key
            arms=clean_results['studies'][key]['results']['arms']
            versus=(arms['uniform']['brier']-arms['optimized']['brier'])/arms['uniform']['brier']
            assert f'{100*versus:+.1f}%' in html_clean, key
            if row['statistical'] is not None:
                assert f'{100*row["statistical"]["relative_improvement"]:+.1f}%' in html_clean, key
        assert (clean.parent/'clean-v1-report.html').exists()
        assert (HERE.parent/'decision_lab/docs/预注册协议-clean-v1.md').exists()
        clean_note=f' clean-v1 summary for {len(clean_summary["rows"])} studies tied to the generated page;'
    direction_note=''
    direction_path=HERE.parent/'decision_lab/reports/cross-study-v1/direction-metrics.json'
    if direction_path.exists():
        direction_data=json.loads(direction_path.read_text())
        html_direction=(HERE/'index.html').read_text()
        assert 'id="direction"' in html_direction
        totals=direction_data['totals']
        assert f'{100*totals["ai_argmax"]:.1f}%' in html_direction
        assert f'{100*totals["reference_argmax"]:.1f}%' in html_direction
        for plan,payload in direction_data['plans'].items():
            for study,block in payload['studies'].items():
                assert f'{100*block["ai_argmax"]:.0f}%' in html_direction,(plan,study)
        quintile=next(b for b in direction_data['plans'].values() if b['deviation'].get('available'))
        assert f'{quintile["deviation"]["quintiles"][-1]["ai_advantage"]:+.3f}' in html_direction
        direction_note=(f' direction metrics for {totals["studies"]} studies / {totals["cards"]} cards '
                        f'tied to the page;')
    anchor_note=''
    anchor_path=HERE.parent/'decision_lab/reports/cross-study-v1/anchor-v1-results.json'
    if anchor_path.exists():
        anchor_data=json.loads(anchor_path.read_text())
        html_anchor=(HERE/'index.html').read_text()
        assert 'id="anchor"' in html_anchor
        for study,entry in anchor_data['studies'].items():
            contrasts=entry['results']['contrasts']
            for key in ('optimized__to__anchored','stratum_history__to__anchored'):
                value=contrasts[key]['relative_improvement']
                assert f'{100*value:+.1f}%' in html_anchor,(study,key)
            for arm in ('optimized','anchored','bounded'):
                assert f'{entry["results"]["arms"][arm]["brier"]:.3f}' in html_anchor,(study,arm)
        anchor_note=(f' anchor-v1 for {len(anchor_data["studies"])} studies tied to the page;')
    print(f'PASS: {checked} source hashes; all local report links; 13 distributions and averages; latest run exclusion; readable labels.'+cross_note+cluster_note+clean_note+wide_note+direction_note+anchor_note)


if __name__=='__main__':
    main()
