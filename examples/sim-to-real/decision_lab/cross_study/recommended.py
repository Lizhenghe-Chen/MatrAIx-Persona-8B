"""Recommended configuration for survey simulation, from the cross-study evidence.

This is a recommendation for the experiment layer only. It does not change any
production default.
"""

OUTPUT_MODE = 'probabilities'
PROMPT_VARIANT = 'optional'

REFERENCE_PREFERENCE = ('stratum_history', 'history', 'attribute_logit')
REFERENCE_REASON = {
    'stratum_history': 'same cards answered by non-evaluated respondents in the same age and education stratum',
    'history': 'same cards answered by non-evaluated respondents overall',
    'attribute_logit': 'conditional logit on displayed attributes, fitted off the evaluated cohort, '
                       'for randomised conjoint cards with no repeated questionnaire',
}

GATES = {
    'minimum_people_per_card': 20,
    'brier_relative_improvement': 0.02,
    'card_error_improvement_pp': 2.0,
    'repeats': 2000,
    'seed': 20261109,
}

EVIDENCE = {
    'probability_output': (
        'Cross-study six-study run: switching the native prompt to probability output improved Brier by '
        '+22% to +43% in every study, while changing only the prompt (keeping single choice) contributed '
        'close to zero. Most of the gain therefore comes from the output format, not the wording.'),
    'prompt_variant': (
        'Same run: prompt_only versus original is +2.6% at best and negative in four of six studies, '
        'so the prediction wording is not a default recommendation.'),
    'statistical_reference': (
        'Same run: no study beat its same-information reference (differences of -8% to -27% in Brier, '
        'all intervals below zero). A reference must therefore be reported with every simulation, and '
        'when it is unavailable the comparison has no meaning.'),
    'distribution_claims': (
        'Cards with fewer than 20 evaluated respondents are excluded: the dryer study has at most 8 people '
        'per card and the Swiss study one, so population-share claims are not estimable there. Using them '
        'produced a spurious -11 point result before the rule was applied.'),
}

LIMITS = [
    'Survey choice prediction only; not purchase, conversion or real behaviour.',
    'Personas are synthetic and not measured attributes of the evaluated respondents.',
    'Public questionnaires may already be in model training data.',
    'Each question is requested separately; joint answer structure is not reproduced.',
]


def choose_reference(available):
    """Return the strongest reference the data can support, or None.

    `available` maps a reference name to whether it can be fitted without the
    evaluated people's answers.
    """
    for name in REFERENCE_PREFERENCE:
        if available.get(name):
            return name
    return None


def required_comparators(available):
    """A run may report the chosen reference; the rest stay optional diagnostics."""
    chosen = choose_reference(available)
    if chosen is None:
        raise ValueError('No same-information reference can be fitted; the study cannot support a comparison')
    return chosen


def claim(brier_comparison, card_comparison, people_per_card=None):
    """Turn the two gates into an explicit claim level.

    Returns one of: no_reference, not_estimable, improvement, direction_only,
    regression, no_evidence.
    """
    if brier_comparison is None:
        return 'no_reference'
    low, _high = brier_comparison['improvement_95_ci']
    relative = brier_comparison.get('relative_improvement')
    if card_comparison is not None and card_comparison.get('available') is False:
        if relative is not None and relative >= GATES['brier_relative_improvement'] and low > 0:
            return 'direction_only'
        return 'not_estimable'
    if relative is not None and relative >= GATES['brier_relative_improvement'] and low > 0:
        if card_comparison is None:
            return 'direction_only'
        card_low = card_comparison['improvement_95_ci'][0]
        if (card_comparison.get('improvement_pp') or 0) >= GATES['card_error_improvement_pp'] and card_low > 0:
            return 'improvement'
        return 'direction_only'
    if _high < 0:
        return 'regression'
    return 'no_evidence'


def configuration():
    return {
        'output_mode': OUTPUT_MODE,
        'prompt_variant': PROMPT_VARIANT,
        'reference_preference': list(REFERENCE_PREFERENCE),
        'reference_reason': dict(REFERENCE_REASON),
        'gates': dict(GATES),
        'evidence': dict(EVIDENCE),
        'limits': list(LIMITS),
    }
