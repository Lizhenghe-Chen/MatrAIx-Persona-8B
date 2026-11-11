"""Hash every private experiment file so a handoff can prove nothing drifted."""
import argparse, datetime, hashlib, json, os
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('Root must be a directory')
    files = []
    for path in sorted(p for p in root.rglob('*') if p.is_file() and not p.is_symlink()):
        if path.name == 'handoff-file-manifest.json':
            continue
        stat = path.stat()
        files.append({'path': path.relative_to(root).as_posix(), 'bytes': stat.st_size,
                      'sha256': digest(path)})
    return {'created_at': datetime.datetime.now().astimezone().isoformat(), 'files': files}


def verify(root, manifest):
    root = Path(root)
    missing, changed = [], []
    for entry in manifest['files']:
        path = root / entry['path']
        if not path.exists():
            missing.append(entry['path'])
        elif path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            changed.append(entry['path'])
    return {'unchanged': len(manifest['files']) - len(missing) - len(changed),
            'missing': missing, 'changed': changed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        result = verify(args.root, json.loads(args.output.read_text()))
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if not result['missing'] and not result['changed'] else 1)
    if args.output.exists():
        raise ValueError('Do not overwrite an existing handoff manifest')
    result = build(args.root)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    os.chmod(args.output, 0o600)
    print(json.dumps({'files': len(result['files']), 'created_at': result['created_at']}))
