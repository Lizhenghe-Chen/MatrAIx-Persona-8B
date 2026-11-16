"""Germany packaging transfer screen, using the actual questionnaire card order."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
import re

import numpy as np
from pypdf import PdfReader
import pyreadstat
from scipy.special import softmax

import protocol
from order_screen import WORK, encode, read, result_path, send

RUN = WORK / 'packaging-transfer-v1'
SOURCE = WORK / 'materials/findrik'
HASHES = {'data_valid.sav':'26bee797ed2075bcaa8d335fc728fb37',
          'survey_original.pdf':'5b0bb3412b74165acb5b214841a1e63e'}
CONTEXT = ('Deutschland, November 2024. Simulierter Einkauf von Kirschtomaten (250 g). '
           'Treffen Sie die Wahl möglichst realistisch. Wenn Sie selbst keine Tomaten essen, '
           'stellen Sie sich vor, dass Sie diese für Freunde oder Familie kaufen. '
           'Die angegebenen Beträge sind Verpackungspreise.')
PRIOR = (' Eine frühere Schweizer Studie untersuchte erzwungene Produktwahlen. Ein statistisches Modell '
         'ergab dort ungefähr 0,28 Log-Odds Vorteil pro niedrigerer Preisstufe und 1,09 pro besserer '
         'Stufe des gesamten Lebenszyklus-Umwelteinflusses. Verwenden Sie dies als unsichere Orientierung. '
         'Verpackungspreis und biologische Abbaubarkeit sind andere Merkmale. Die Schweizer Studie '
         'enthält keine Information über die Wahrscheinlichkeit, nichts zu kaufen.')


def cards():
    design = {}
    for page in PdfReader(SOURCE/'survey_original.pdf').pages:
        text = page.extract_text()
        match = re.search(r'Choice(\d\d)', text)
        if match is None:
            continue
        offers = re.findall(
            r'Verpackung:\s*(Biokunststoff|[Kk]onventioneller\s+Kunststoff)\s+'
            r'(Biologisch abbaubar|Nicht biologisch abbaubar)\s+'
            r'Produkt hält (\d+) Tage länger\s+Preis Verpackung:\s*(0,\d+) EUR', text)
        if len(offers) != 3 or 'Keines dieser 3 Produkte' not in text:
            raise ValueError(f'Incomplete original choice card {match[0]}')
        design[match[0]] = [(' '.join(m.split()),d,int(days),float(price.replace(',','.')))
                            for m,d,days,price in offers]
    if set(design) != {f'Choice{i:02}' for i in range(1,13)}:
        raise ValueError('Original survey choice cards do not match response columns')
    return design


def freeze():
    for name, digest in HASHES.items():
        if hashlib.md5((SOURCE/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Source checksum changed: {name}')
    design = cards()
    jobs = []
    for qid, profiles in design.items():
        opts = {str(i):f'Verpackung: {material}. {decay}. Produkt hält {days} Tage länger. '
                       f'Preis Verpackung: {price:.2f} EUR.'
                for i,(material,decay,days,price) in enumerate(profiles,1)}
        opts['0'] = 'Keines dieser 3 Produkte'
        question = {'id':qid,'prompt':'Welches dieser Produkte würden Sie kaufen?','options':opts}
        for condition, prior in [('direct',''),('source_hint',PRIOR)]:
            payload = {'title':'Auswahlentscheidungen: Kirschtomaten','context':CONTEXT+prior,
                       'questions':[question],'basic':{}}
            jobs.append({'study':condition,'questions':[question],
                         'body':protocol.build(payload,'basic','qwen',{}, {},512)})
    np.random.default_rng(20261109).shuffle(jobs)
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes() != encode(jobs):
        raise ValueError('Frozen inputs changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    return jobs


def score(jobs):
    frame, meta = pyreadstat.read_sav(str(SOURCE/'data_valid.sav'))
    assert meta.variable_value_labels['Group'][2] == 'G2: without information about bioplastic'
    design = cards()
    target = frame.loc[frame.Group==2,list(design)].to_numpy()
    if not np.isin(target,[0,1,2,3]).all():
        raise ValueError('Unexpected missing or invalid response code')
    y = np.eye(4)[target.astype(int)]
    bought = target!=0
    by_condition = {}
    identities = set()
    missing = failed = 0
    for job in jobs:
        path = result_path(job,RUN)
        if not path.exists():
            missing += 1
            continue
        result = read(path)
        if result['status'] != 'ok':
            failed += 1
            continue
        identities.add(json.dumps(result['identity'],sort_keys=True))
        by_condition.setdefault(job['study'],{}).update(result['p'])
    if len(identities) > 1:
        raise ValueError('Model identity changed')
    out = {'people':len(y),'cards':len(design),'requests':len(jobs),'missing':missing,'failed':failed,
           'actual_no_buy_rate':float(y[:,:,0].mean()),'methods':{}}
    if missing or failed:
        return out
    swiss = read(WORK/'attribute-transfer-v1/frozen.json')['beta']
    arrays = {'uniform_conditional': np.full((12,3),1/3)}
    price = np.asarray([[p[3] for p in profiles] for profiles in design.values()])
    biodegradable = np.asarray([[p[1]=='Biologisch abbaubar' for p in profiles] for profiles in design.values()])
    # Stress tests only. One German packaging-price step is EUR 0.15.
    # One biodegradable label is provisionally one impact step.
    arrays['swiss_price_only'] = softmax(-swiss[0]*price/.15, axis=1)
    arrays['swiss_proxy_only'] = softmax(swiss[1]*biodegradable, axis=1)
    arrays['swiss_price_and_proxy'] = softmax(-swiss[0]*price/.15+swiss[1]*biodegradable,axis=1)
    for name, probabilities in by_condition.items():
        p = np.asarray([[probabilities[q][str(i)] for i in range(4)] for q in design])
        if np.any(p[:,1:].sum(axis=1)==0):
            raise ValueError('Cannot condition on purchase when model assigns it zero probability')
        arrays[name] = p[:,1:]/p[:,1:].sum(axis=1,keepdims=True)
        out['methods'][name] = {'full_brier':float(np.sum((p-y)**2,axis=-1).mean()),
                                'predicted_no_buy_rate':float(p[:,0].mean())}
    loo = (y.sum(axis=0)-y)/(len(y)-1)
    out['methods']['german_same_card_loo'] = {'full_brier':float(np.sum((loo-y)**2,axis=-1).mean())}
    product = loo[:,:,1:]
    arrays['german_same_card_loo'] = product/product.sum(axis=-1,keepdims=True)
    people_losses = {}
    for name, p in arrays.items():
        loss = np.sum((p-y[:,:,1:])**2,axis=-1)
        losses = (loss*bought).sum(axis=1)/np.maximum(bought.sum(axis=1),1)
        losses = losses[bought.any(axis=1)]
        people_losses[name] = losses
        out['methods'].setdefault(name,{})['conditional_brier_person_mean'] = float(losses.mean())
    rng = np.random.default_rng(20261109)
    out['conditional_differences'] = {}
    for label,baseline,candidate in [
        ('hint_vs_direct','direct','source_hint'),
        ('price_vs_uniform','uniform_conditional','swiss_price_only'),
        ('joint_vs_price','swiss_price_only','swiss_price_and_proxy'),
        ('joint_vs_direct','direct','swiss_price_and_proxy'),
        ('joint_vs_proxy','swiss_proxy_only','swiss_price_and_proxy'),
    ]:
        delta = people_losses[baseline]-people_losses[candidate]
        boot = delta[rng.integers(len(delta),size=(2000,len(delta)))].mean(axis=1)
        out['conditional_differences'][label] = {'baseline':baseline,'candidate':candidate,'improvement':float(delta.mean()),
             'ci95_fixed_cards_and_predictions':np.quantile(boot,[.025,.975]).tolist()}
    out['model_identity'] = [json.loads(i) for i in sorted(identities)]
    return out


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=['freeze','run','score'])
    action = cli.parse_args().action
    jobs = freeze() if action != 'score' else read(RUN/'jobs.json')
    if action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs))
    print(json.dumps(score(jobs) if action=='score' else {'jobs':len(jobs)},indent=2))
