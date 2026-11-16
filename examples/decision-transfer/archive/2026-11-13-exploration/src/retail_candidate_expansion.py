"""Evaluate title search and Qwen query expansion over the historical catalogue."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json
import random
import urllib.request

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from order_screen import SEED, URL, WORK, encode, read, result_path
from protocol import MODELS
from retail_next_basket import read_orders
from retail_rerank_controls import N as CONTROL_N, SOURCE_HASH
from retail_unseen_rerank import N as PRIOR_N, SOURCE, catalogue_and_cases

RUN = WORK / 'retail-candidate-expansion-v1'
N = 120
K = 20


def prepare():
    if sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError('Unexpected source version')
    names, cases = catalogue_and_cases()
    history, _, market, _ = read_orders(SOURCE)
    products = sorted({item for _, basket in market for item in basket if item in names})
    all_ids = sorted(cases)
    prior = set(random.Random(SEED).sample(all_ids, PRIOR_N))
    controls = set(random.Random(SEED + 1).sample([i for i in all_ids if i not in prior], CONTROL_N))
    customers = random.Random(SEED + 2).sample([i for i in all_ids if i not in prior | controls], N)
    jobs, scoring = [], []
    for customer in customers:
        before, related, popular, actual = cases[customer]
        query = ' '.join(names[item] for basket in before for item in basket)
        lines = ['; '.join(names[item] for item in basket) for basket in before]
        prompt = ('Given these two historical orders from a UK gift retailer, suggest up to 12 '
                  'short English product-search phrases for related products the shopper might buy later. '
                  'Include closely related uses or complementary items, using words that could appear '
                  'in a product title. Return only JSON with a phrases array of distinct strings.\n'
                  f'Older order: {lines[0]}\nMore recent order: {lines[1]}')
        body = {'model': MODELS['qwen'], 'temperature': .7, 'top_p': 1,
                'max_tokens': 512, 'response_format': {'type': 'json_object'},
                'chat_template_kwargs': {'enable_thinking': False},
                'messages': [{'role': 'user', 'content': prompt}]}
        jobs.append({'body': body})
        older = {item for basket in history[customer] for item in basket}
        scoring.append((query, older, actual, related, popular))
    return names, products, jobs, scoring


def send(job, directory):
    path = result_path(job, directory)
    if path.exists():
        return
    marker = path.with_suffix('.pending')
    try:
        marker.touch(exist_ok=False)
    except FileExistsError:
        return
    try:
        request = urllib.request.Request(URL, data=encode(job['body']),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=45) as response:
            raw = json.load(response)
        choice, = raw['choices']
        identity = {key: raw.get(key) for key in ('model', 'system_fingerprint')}
        message = choice['message']
        if identity['model'] != MODELS['qwen'] or choice['finish_reason'] != 'stop' or any(
            message.get(key) for key in ('reasoning_content', 'tool_calls')
        ):
            raise ValueError('Incomplete or unexpected model response')
        content = json.loads(message['content'])
        phrases = content['phrases']
        if set(content) != {'phrases'} or not isinstance(phrases, list) or not 1 <= len(phrases) <= 12 or any(
            not isinstance(phrase, str) or not 1 <= len(phrase.strip()) <= 100 for phrase in phrases
        ) or len(set(phrase.casefold().strip() for phrase in phrases)) != len(phrases):
            raise ValueError('Invalid search phrases')
        result = {'status': 'ok', 'phrases': phrases, 'identity': identity}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'status': 'error', 'type': type(error).__name__}
    temp = path.with_suffix('.tmp')
    temp.write_bytes(encode(result))
    temp.replace(path)
    marker.unlink()


def evaluate(names, products, jobs, scoring):
    titles = [names[item] for item in products]
    word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    char = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), sublinear_tf=True)
    word_docs, char_docs = word.fit_transform(titles), char.fit_transform(titles)
    positions = {item: i for i, item in enumerate(products)}
    methods = ('old_union', 'title_search', 'qwen_phrases', 'title_with_qwen',
               'related_with_title', 'related_with_title_and_qwen')
    values, identities, failures = [], set(), Counter()
    any_hit, nonlexical_hits = Counter(), Counter()
    catalogue_targets = 0
    target_total = 0
    for job, (query, older, actual, related, popular) in zip(jobs, scoring, strict=True):
        path = result_path(job, RUN)
        result = read(path) if path.exists() else {'status': 'error', 'type': 'missing'}
        if result['status'] != 'ok':
            failures[result['type']] += 1
            continue
        identities.add(json.dumps(result['identity'], sort_keys=True))
        words = (word.transform([query]) @ word_docs.T).toarray()[0]
        chars = (char.transform([query]) @ char_docs.T).toarray()[0]
        expanded = (word.transform(result['phrases']) @ word_docs.T).max(axis=0).toarray()[0]
        eligible = np.asarray([item not in older for item in products])

        def top(scores):
            rank = np.argsort(-scores, kind='stable')
            return [products[i] for i in rank if eligible[i] and scores[i] > 0][:K]

        lexical = (words + chars) / 2
        title, mixed = top(lexical), top(.75 * lexical + .25 * expanded)
        picks = (list(dict.fromkeys([*related, *popular]))[:K], title,
                 top(expanded), mixed, list(dict.fromkeys([*related, *title]))[:K],
                 list(dict.fromkeys([*related, *mixed]))[:K])
        catalogue_targets += len(actual & positions.keys())
        target_total += len(actual)
        row = []
        for method, chosen in zip(methods, picks, strict=True):
            hits = actual.intersection(chosen)
            row.append(len(hits))
            any_hit[method] += bool(hits)
            nonlexical_hits[method] += sum(1 for item in hits if item in positions and words[positions[item]] == 0)
        values.append(row)
    if len(identities) != 1 or not values:
        raise ValueError('Missing or mixed model identity')
    values = np.asarray(values)
    boot = np.random.default_rng(SEED).integers(len(values), size=(2000, len(values)))
    improvements = {}
    for label, candidate, base in (
        ('add_qwen_to_title', 3, 1),
        ('add_title_to_related_vs_old_union', 4, 0),
        ('add_qwen_to_related_and_title', 5, 4),
    ):
        delta = values[:, candidate] - values[:, base]
        improvements[label] = {'hits_per_order': float(delta.mean()),
                               'interval_95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()}
    return {'source_sha256': SOURCE_HASH, 'seed': SEED + 2, 'candidate_limit': K,
            'catalogue_size': len(products), 'expected': len(jobs), 'valid': len(values),
            'failures': dict(failures), 'identity': json.loads(identities.pop()),
            'target_items': target_total, 'target_items_in_catalogue': catalogue_targets,
            'hits': dict(zip(methods, values.sum(axis=0).tolist(), strict=True)),
            'orders_with_hit': dict(any_hit), 'hits_without_word_overlap': dict(nonlexical_hits),
            'comparisons': improvements}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    names, products, jobs, scoring = prepare()
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=RUN), jobs))
    print(json.dumps(evaluate(names, products, jobs, scoring), indent=2))


if __name__ == '__main__':
    main()
