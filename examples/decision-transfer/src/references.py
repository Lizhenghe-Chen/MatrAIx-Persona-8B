"""Same-information statistical references.

Two references answer "what can be done without knowing the person":
a constant that only uses the group's marginal choice share, and a conditional logit
that only uses the attributes printed on the card. Both are fitted leave-one-person-out
so the person being predicted never contributes to their own reference.
"""
import math
import re

import numpy as np

import payloads

LEVELS = ['very low', 'low', 'medium', 'high', 'very high']
LABEL_TO_PRODUCT = {label.lower(): product for product, label in payloads.PRODUCT_LABEL.items()}


def attribute_ranks(question):
    """Return (price_rank, impact_rank) per option id, from the frozen labels."""
    ranks = {}
    for option_id, label in question['options'].items():
        low = label.lower()
        product = next((name for prefix, name in LABEL_TO_PRODUCT.items() if low.startswith(prefix)), None)
        if product is None:
            raise ValueError('Unknown product in label: ' + label)
        amount = re.search(r'price ([0-9.]+) chf', low)
        if amount is None:
            raise ValueError('Missing price in label: ' + label)
        value = float(amount.group(1))
        levels = payloads.PRICE_LEVELS[product]
        price = min(range(len(levels)), key=lambda i: abs(levels[i] - value))
        impact = next((i for i, word in enumerate(LEVELS) if f'impact {word}' in low), None)
        if impact is None:
            raise ValueError('Missing impact in label: ' + label)
        ranks[option_id] = (price, impact)
    return ranks


def _two_option(probability_green, question, green_option):
    options = list(question['options'])
    p = [probability_green if option == green_option else 1 - probability_green for option in options]
    return p


def green_option(question):
    ranks = attribute_ranks(question)
    return min(ranks, key=lambda option: (ranks[option][1], ranks[option][0]))


def choose_green(answers, question):
    return answers[question['id']] == green_option(question)


def loo_base_rate(deck, answers, person):
    """Marginal share of greener choices among the other participants."""
    picks = []
    for rig, questions in deck.items():
        if str(rig) == str(person):
            continue
        for question in questions:
            picks.append(choose_green(answers[str(rig)], question))
    return float(np.mean(picks)) if picks else 0.5


def _fit_logit(rows):
    """Conditional logit on (impact difference, price difference); no person features."""
    def negative_log_likelihood(beta):
        total = 0.0
        for impact_gap, price_gap, chose_green in rows:
            score = beta[0] * impact_gap + beta[1] * price_gap
            score = max(min(score, 30.0), -30.0)
            p = 1 / (1 + math.exp(-score))
            p = min(max(p, 1e-9), 1 - 1e-9)
            total += -math.log(p if chose_green else 1 - p)
        return total + 1e-4 * float(beta @ beta)

    best = np.zeros(2)
    best_value = negative_log_likelihood(best)
    for impact_start in (0.5, 1.0, 2.0, 3.0):
        for price_start in (-0.2, -0.5, -1.0):
            beta = np.array([impact_start, price_start])
            value = negative_log_likelihood(beta)
            step = 0.5
            while step > 1e-3:
                improved = False
                for delta in (np.array([step, 0.0]), np.array([-step, 0.0]),
                              np.array([0.0, step]), np.array([0.0, -step])):
                    candidate = beta + delta
                    candidate_value = negative_log_likelihood(candidate)
                    if candidate_value < value:
                        beta, value, improved = candidate, candidate_value, True
                        break
                if not improved:
                    step /= 2
            if value < best_value:
                best, best_value = beta, value
    return best


def loo_conditional_logit(deck, answers, person):
    """Attributes-only reference, fitted on the other participants."""
    rows = []
    for rig, questions in deck.items():
        if str(rig) == str(person):
            continue
        for question in questions:
            ranks = attribute_ranks(question)
            options = list(question['options'])
            green = green_option(question)
            other = [option for option in options if option != green][0]
            impact_gap = ranks[other][1] - ranks[green][1]
            price_gap = ranks[other][0] - ranks[green][0]
            rows.append((float(impact_gap), float(price_gap), bool(choose_green(answers[str(rig)], question))))
    beta = _fit_logit(rows)
    return beta


def predict_logit(beta, question):
    ranks = attribute_ranks(question)
    options = list(question['options'])
    green = green_option(question)
    other = [option for option in options if option != green][0]
    score = beta[0] * (ranks[other][1] - ranks[green][1]) + beta[1] * (ranks[other][0] - ranks[green][0])
    return 1 / (1 + math.exp(-max(min(score, 30.0), -30.0)))


def build(requests, answers):
    """Reference probabilities over the frozen two-option questions, keyed by person/question."""
    deck = {}
    for request in requests:
        if request.get('role') != 'evaluation':
            continue
        deck[request['rig']] = request['questions']
    out = {}
    betas = {}
    for rig in deck:
        rate = loo_base_rate(deck, answers, rig)
        beta = loo_conditional_logit(deck, answers, rig)
        betas[str(rig)] = [round(float(beta[0]), 4), round(float(beta[1]), 4)]
        for question in deck[rig]:
            green = green_option(question)
            out[(str(rig), question['id'])] = {
                'base_rate': _two_option(rate, question, green),
                'logit': _two_option(predict_logit(beta, question), question, green),
            }
    return out, betas
