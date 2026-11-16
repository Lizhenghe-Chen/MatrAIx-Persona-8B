"""Evaluate small local pilots on disjoint people and choice cards, offline."""
import json
import re

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit, softmax

from choice_predictor import fit_products

import optout_transfer as transfer
from order_screen import read, WORK, SEED

SIZES = (10, 25, 50, 100)
PSEUDO_CHOICE_MASS = 15.0
REPEATS = 100


def load():
    beer_deck, beer_people = transfer.beer_deck()
    german_deck, german_people = transfer.german_deck()
    beer_p, beer_ids = transfer.predictions(beer_deck, transfer.RUN)
    german_p, german_ids = transfer.predictions(german_deck, transfer.germany.RUN)
    if beer_ids != german_ids or len(beer_ids) != 1:
        raise ValueError('Inconsistent Qwen identity')
    beer = transfer.outcome(beer_p, beer_people)
    german = transfer.outcome(german_p, german_people)
    # Group by underlying card ID. Beer has different IDs for the two blocks,
    # but the same ID across information conditions.
    beer_keys = np.asarray([[key[1] for key in person] for person in beer_people])
    german_keys = np.asarray([list(person) for person in german_people])
    beta = read(WORK/'attribute-transfer-v1/frozen.json')['beta']
    design = transfer.germany.cards()
    german_products = {
        card:softmax([-beta[0]*price/.15+beta[1]*(decay=='Biologisch abbaubar')
                      for _,decay,_,price in profiles])
        for card, profiles in design.items()
    }
    prior = np.asarray([[german_products[key] for key in row] for row in german_keys])
    beer_features = {}
    for key, job in beer_deck.items():
        options = job['questions'][0]['options']
        beer_features[key] = [beer_attributes(options[i]) for i in ('1','2')]
    bx = np.asarray([[beer_features[key] for key in person] for person in beer_people])
    gx = np.asarray([[[[float(material.lower()=='biokunststoff'),
                       float(decay=='Biologisch abbaubar'), (days-5)/2, (price-.45)/.15]
                       for material,decay,days,price in design[key]] for key in row] for row in german_keys])
    return {'beer':(*beer,beer_keys,None,bx), 'german':(*german,german_keys,prior,gx)}


def beer_attributes(label):
    price = float(re.search(r'price: \$([0-9.]+)',label)[1])
    return [float('packaging: Can' in label), *(float(f'{field}: Yes' in label)
            for field in ('water_conserving','energy_conserving','waste_reduction','local')), (price-9)/1.5]


def split_cards(keys, rng):
    selected = []
    # Each beer participant sees eight cards from one block. Split every
    # block equally, while keeping the same card together across instructions.
    for block in np.unique(keys,axis=0):
        cards = sorted(set(block))
        if len(cards)!=keys.shape[1]:
            raise ValueError('Unexpected repeated card within a block')
        if set(cards) & set(selected):
            if set(cards).issubset(selected):
                continue
            raise ValueError('Partially overlapping card blocks')
        selected.extend(rng.permutation(cards)[:len(cards)//2])
    mask = np.isin(keys,selected)
    if not np.all(mask.sum(axis=1)==keys.shape[1]//2):
        raise ValueError('Unbalanced card split')
    return mask


def losses(rate, products, target):
    joint = np.column_stack([rate,products*(1-rate[:,None])])
    return float(np.sum((joint-target)**2,axis=1).mean())


def select_blend_weight(features, targets, candidate, keys, pilot_mask):
    """Cross-fit within pilot, holding out people and card IDs together."""
    n = len(targets)
    person_fold = np.arange(n) % 5
    card_fold = {}
    for block in np.unique(keys, axis=0):
        for index, card in enumerate(sorted(set(block) & set(keys[pilot_mask]))):
            if card in card_fold and card_fold[card] != index % 3:
                raise ValueError('Card has inconsistent fold')
            card_fold[card] = index % 3
    card_partition = np.asarray([[card_fold.get(card,-1) for card in row] for row in keys])
    total_numerator = total_denominator = 0.0
    validated = 0
    for person_group in range(5):
        for card_group in range(3):
            validation = pilot_mask & (person_fold[:,None]==person_group) & (card_partition==card_group)
            if not validation.any():
                continue
            training = pilot_mask & (person_fold[:,None]!=person_group) & (card_partition!=card_group)
            if not training.any():
                return 0.0
            beta = fit_products(features[training],targets[training])
            products = softmax(features[validation] @ beta, axis=1)
            # Common refusal rate cancels in the binary term. Evaluate the
            # entire joint Brier including refusal rows using training-only rate.
            rate = (targets[training,0].sum()+.5)/(training.sum()+1)
            baseline = (1-rate)*products
            step = (1-rate)*(candidate[validation]-products)
            error = targets[validation,1:] - baseline
            total_numerator += float(np.sum(step*error))
            total_denominator += float(np.sum(step**2))
            validated += validation.sum()
    if validated!=pilot_mask.sum():
        raise ValueError('Inner validation did not cover every pilot record')
    return float(np.clip(total_numerator/total_denominator,0,1)) if total_denominator else 0.0


def evaluate(p, y, keys, prior, features, *, adaptive=False, attribute_prior=False, shrinkage=False):
    rng = np.random.default_rng(SEED)
    raw = p[:,:,0]
    purchase = p[:,:,1:].sum(axis=2,keepdims=True)
    # A refusal-only model response gives no ranking of purchase alternatives.
    conditional = np.divide(p[:,:,1:], purchase, where=purchase>0,
                            out=np.full_like(p[:,:,1:],1/(p.shape[2]-1)))
    if not np.isfinite(conditional).all():
        raise ValueError('Invalid purchase conditional probabilities')
    logits = logit(np.clip(raw,1e-5,1-1e-5))
    rows = {size:[] for size in SIZES}
    for _ in range(REPEATS):
        fit_cards = split_cards(keys,rng)
        order = rng.permutation(len(y))
        # The same held-out people and cards evaluate every calibration budget.
        test_people = order[max(SIZES):]
        test = ~fit_cards[test_people]
        targets = y[test_people][test]
        original = raw[test_people][test]
        qwen_products = conditional[test_people][test]
        test_logits = logits[test_people][test]
        for size in SIZES:
            train_people = order[:size]
            train = fit_cards[train_people]
            train_targets = y[train_people][train]
            train_y = train_targets[:,0]
            train_logits = logits[train_people][train]
            # Jeffreys smoothing keeps estimates finite when a pilot has zero opt-outs.
            rate = (train_y.sum()+.5)/(len(train_y)+1)
            offset = brentq(lambda b: expit(train_logits+b).mean()-rate,-30,30)
            calibrated = expit(test_logits+offset)
            common_rate = np.full_like(original,rate)
            uniform = np.full_like(qwen_products,1/qwen_products.shape[1])
            position_counts = train_targets[:,1:].sum(axis=0) + .5
            position_share = np.broadcast_to(position_counts/position_counts.sum(), qwen_products.shape)
            beta = fit_products(features[train_people][train],train_targets)
            fitted_products = softmax(features[test_people][test] @ beta,axis=1)
            methods = {
                'pilot_attribute_logit':(common_rate,fitted_products),
                'pilot_attribute_logit_qwen_mix':(common_rate,(fitted_products+qwen_products)/2),
                'pilot_uniform_products':(common_rate,uniform),
                'pilot_position_products':(common_rate,position_share),
                'qwen':(original,qwen_products),
                'pilot_constant':(common_rate,qwen_products),
                'pilot_offset':(calibrated,qwen_products),
            }
            if prior is not None:
                product_prior = prior[test_people][test]
                methods.update({
                    'swiss_products_qwen':(original,product_prior),
                    'swiss_products_pilot_constant':(np.full_like(original,rate),product_prior),
                    'swiss_products_pilot_offset':(calibrated,product_prior),
                    'pilot_attribute_logit_swiss_mix':(common_rate,(fitted_products+product_prior)/2),
                })
            if attribute_prior:
                x_train = features[train_people][train]
                q_train = conditional[train_people][train]
                x_test = features[test_people][test]
                # Unique stimulus/probability pairs, not one synthetic answer per person.
                flat = np.column_stack((x_train.reshape(len(x_train),-1),q_train))
                _, index = np.unique(flat,axis=0,return_index=True)
                pseudo_x, pseudo_q = x_train[index], q_train[index]
                neutral = np.full_like(pseudo_q,1/pseudo_q.shape[1])
                for name, pseudo_y in [('qwen_attribute_prior',pseudo_q),('neutral_attribute_prior',neutral)]:
                    coefficients = fit_products(x_train,train_targets,pseudo=(pseudo_x,pseudo_y,PSEUDO_CHOICE_MASS))
                    methods[name] = (common_rate,softmax(x_test @ coefficients,axis=1))
            uniform_weight = 0.0
            if shrinkage:
                shape = conditional[train_people].shape
                uniform_input = np.full(shape,1/shape[-1])
                uniform_weight = select_blend_weight(features[train_people],y[train_people],
                                                    uniform_input,keys[train_people],train)
                methods['cross_validated_shrinkage'] = (
                    common_rate,(1-uniform_weight)*fitted_products+uniform_weight*uniform)
                fixed_weight = 25/(size+25)
                methods['fixed_shrinkage'] = (
                    common_rate,(1-fixed_weight)*fitted_products+fixed_weight*uniform)
            weight = 0.0
            if adaptive:
                weight = select_blend_weight(features[train_people],y[train_people],
                                            conditional[train_people],keys[train_people],train)
                methods['pilot_adaptive_mix'] = (common_rate,(1-weight)*fitted_products+weight*qwen_products)
            rows[size].append({
                name:{'full_brier':losses(q,products,targets),
                      'no_buy_brier':float(np.mean(2*(q-targets[:,0])**2)),
                      'no_buy_rate':float(q.mean()),
                      **({'qwen_weight':weight} if name=='pilot_adaptive_mix' else {}),
                      **({'uniform_weight':uniform_weight} if name=='cross_validated_shrinkage' else {})}
                for name,(q,products) in methods.items()
            })
    output = {}
    for size, trials in rows.items():
        output[size] = {}
        for method in trials[0]:
            ref = 'swiss_products_qwen' if method.startswith('swiss_') else 'qwen'
            delta = np.array([r[ref]['full_brier']-r[method]['full_brier'] for r in trials])
            delta_vs_attribute = np.array([r['pilot_attribute_logit']['full_brier']-r[method]['full_brier']
                                           for r in trials])
            delta_vs_simple = np.array([r['pilot_position_products']['full_brier']-r[method]['full_brier']
                                        for r in trials])
            output[size][method] = {
                **{k:float(np.mean([r[method][k] for r in trials])) for k in trials[0][method]},
                'reference':ref,'improvement':float(delta.mean()),
                'improvement_over_pilot_attributes':float(delta_vs_attribute.mean()),
                'positive_splits_vs_pilot_attributes':float(np.mean(delta_vs_attribute>0)),
                'improvement_over_pilot_positions':float(delta_vs_simple.mean()),
                'positive_splits_vs_pilot_positions':float(np.mean(delta_vs_simple>0)),
                'positive_splits':float(np.mean(delta>0)),
                'split_improvement_p05_p95':np.quantile(delta,[.05,.95]).tolist(),
            }
        if attribute_prior:
            delta = np.asarray([r['neutral_attribute_prior']['full_brier']-
                                r['qwen_attribute_prior']['full_brier'] for r in trials])
            output[size]['qwen_attribute_prior'].update({
                'improvement_over_neutral':float(delta.mean()),
                'positive_splits_vs_neutral':float(np.mean(delta>0)),
                'split_improvement_vs_neutral_p05_p95':np.quantile(delta,[.05,.95]).tolist(),
            })
    return {'people':len(y),'actual_no_buy_rate':float(y[:,:,0].mean()),
            'pilot_cards_per_person':keys.shape[1]//2,'test_people_per_split':len(y)-max(SIZES),
            'budgets':output}


if __name__ == '__main__':
    print(json.dumps({'seed':SEED,'splits':REPEATS,'new_calls':0,
                      'studies':{k:evaluate(*v) for k,v in load().items()}},indent=2))
