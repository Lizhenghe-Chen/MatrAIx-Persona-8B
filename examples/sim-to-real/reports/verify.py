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
    print(f'PASS: {checked} source hashes; all local report links; 13 distributions and averages; latest run exclusion; readable labels.')


if __name__=='__main__':
    main()
