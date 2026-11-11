"""Conservative command surface: incomplete audits cannot launch experiments."""
import argparse
import json
from pathlib import Path
from .core.core import digest, split, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'freeze', 'run', 'score', 'report', 'verify'])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--seal', type=Path)
    parser.add_argument('--phase', choices=['train','development','test'])
    args = parser.parse_args()
    doc = json.loads(args.input.read_text())
    if args.command == 'check':
        validate(doc['rows'])
        print(json.dumps({'records': len(doc['rows']), 'people': len({r['person'] for r in doc['rows']})}))
    elif args.command == 'freeze':
        validate(doc['rows'])
        required = ['license_cloud_use', 'question_mapping', 'background_timing', 'author_statistics', 'leakage_review']
        if not all(doc.get('audit', {}).get(k) is True for k in required):
            raise SystemExit('Admission audit incomplete; cannot freeze')
        if not args.output:
            parser.error('--output required')
        if not args.config:
            parser.error('--config required to freeze')
        config = json.loads(args.config.read_text())
        if config.get('status') != 'frozen':
            raise ValueError('Configuration must be frozen')
        result = {'config_sha256': digest(config), 'input_sha256': digest(doc), 'assignments': split(doc['rows']), 'seed': 20261109}
        with args.output.open('x') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    elif args.command == 'run':
        from .core.runner import run
        if not all([args.config, args.seal, args.phase, args.output]):
            parser.error('run requires --config --seal --phase --output checkpoint.sqlite')
        result = run(doc, json.loads(args.seal.read_text()), json.loads(args.config.read_text()), args.output, args.phase)
        print(json.dumps(result))
    elif args.command == 'score':
        from .evaluation.scoring import score
        validate(doc['rows'])
        predictions = {}
        for item in doc['predictions']:
            key = (item['person'], item['task'])
            if key in predictions:
                raise ValueError('Duplicate prediction')
            predictions[key] = item['probabilities']
        result = score(doc['rows'], predictions)
        if not args.output:
            parser.error('--output required')
        with args.output.open('x') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    elif args.command == 'report':
        if doc.get('status')=='complete_test_primary_brier_only':
            from .reporting.study_report import render
        elif doc.get('status')=='complete_population_distribution_analysis':
            from .reporting.population_report import render
        else:
            from .reporting.report import render
        if not args.output:
            parser.error('--output required')
        with args.output.open('x') as f:
            f.write(render(doc))
    elif args.command == 'verify':
        for item in doc['files']:
            import hashlib
            p = args.input.parent / item['path']
            if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
                raise SystemExit('Hash mismatch: ' + item['path'])
        print('Verified')
    else:
        raise SystemExit('Not implemented: ' + args.command + '. No results or API calls were generated.')
