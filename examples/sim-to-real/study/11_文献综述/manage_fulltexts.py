"""Verify frozen full texts, or retrieve missing copies without changing versions.

Uses the Python standard library. No credentials, login automation, or overwrite.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'download'])
    args = parser.parse_args()
    rows = json.loads((ROOT / '全文资料/文件索引.json').read_text())['files']
    failures = 0
    present = 0
    missing_local = 0
    for row in rows:
        path = (ROOT / row['path']).resolve()
        if not path.is_relative_to(ROOT / '全文资料'):
            raise ValueError('File path is outside the literature library')
        if not path.exists() and args.command == 'download':
            temporary = None
            try:
                request = urllib.request.Request(
                    row['download_url'], headers={'User-Agent': 'MatrAIx-Literature-Archive/1.0'}
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                with urllib.request.urlopen(request, timeout=45) as response:
                    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                        temporary = Path(output.name)
                        digest = hashlib.sha256()
                        size = 0
                        while chunk := response.read(1024 * 1024):
                            size += len(chunk)
                            if size > row['bytes']:
                                raise ValueError('Downloaded content exceeds the frozen size')
                            digest.update(chunk)
                            output.write(chunk)
                if size != row['bytes'] or digest.hexdigest() != row['sha256']:
                    raise ValueError('Content differs: possible new version or access challenge')
                # Exclusive creation prevents an existing copy from being overwritten.
                with path.open('xb') as output, temporary.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
            except Exception as exc:
                failures += 1
                print(f"DOWNLOAD FAILED {row['source_id']} {row['role']}: {exc}")
                continue
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        if not path.exists():
            if row['storage'] == 'local_only':
                missing_local += 1
                print(f"LOCAL COPY ABSENT: {row['source_id']} {row['role']}")
            else:
                failures += 1
                print(f"REQUIRED FILE MISSING: {row['path']}")
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if path.stat().st_size != row['bytes'] or digest.hexdigest() != row['sha256']:
            failures += 1
            print(f"CONTENT MISMATCH: {row['path']}")
        else:
            present += 1
    print(f'Verified: {present}; absent local-only copies: {missing_local}; errors: {failures}')
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
