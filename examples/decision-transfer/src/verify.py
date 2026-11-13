"""Verify isolated preparation, source provenance, frozen Git pointer and local links."""
import json,hashlib,re,subprocess
from freeze import HERE,REPO,verify
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 verify()
 frozen=json.loads((HERE/'archive/frozen-history.json').read_text())
 tag=subprocess.check_output(['git','rev-parse',frozen['git_tag']+'^{}'],cwd=REPO,text=True).strip()
 if tag!=frozen['historical_commit']:raise RuntimeError('Historical tag moved')
 refs=json.loads((HERE/'data/reference/provenance.json').read_text())
 for r in refs['files']:
  if sha(HERE/r['copy'])!=r['sha256'] or sha(REPO/r['source'])!=r['sha256']:raise RuntimeError('Reference drift')
 report=(HERE/'reports/index.html').read_text()
 for link in re.findall(r'href="([^"]+)"',report):
  if not link.startswith(('http:','https:','#')) and not (HERE/'reports'/link).is_file():raise RuntimeError('Broken link: '+link)
 if re.search(r'<(?:script|link|img)[^>]+(?:src|href)="https?://',report):raise RuntimeError('Offline report has network asset')
 candidates=json.loads((HERE/'data/candidates.json').read_text())
 if candidates['model_calls']!=0 or any(c['admitted'] for c in candidates['candidates']):raise RuntimeError('Unexpected run/admission in preparation version')
 changed=subprocess.check_output(['git','status','--porcelain','--','examples/sim-to-real'],cwd=REPO,text=True).strip()
 if changed:raise RuntimeError('Historical directory modified')
 print('PASS: tag, copied references, report links, zero model calls, no historical writes.')
if __name__=='__main__':main()
