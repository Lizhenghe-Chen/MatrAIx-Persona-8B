"""Model-facing payloads for the Swiss study. Answers never enter this module.

Attribute levels and wording come from the paper's Table 1 and the authors'
supplementary full questionnaire (A.10). Prices are the published CHF levels.
"""
import swiss

PRICE_LEVELS = {
    'Chocolate (100g)': [2.70, 2.85, 3.00, 3.15, 3.30],
    'Tomatoes (1kg)': [4.50, 4.75, 5.00, 5.25, 5.50],
    'Shirt': [34.0, 36.0, 38.0, 40.0, 42.0],
    'Jacket': [135.0, 143.0, 150.0, 158.0, 165.0],
    'Smartphone': [450.0, 475.0, 500.0, 525.0, 550.0],
    'Laptop': [1260.0, 1330.0, 1400.0, 1470.0, 1540.0],
}
PRICE_ORDER = ['Very low price', 'Low price', 'Medium price', 'High price', 'Very high price']
IMPACT_ORDER = ['Very low', 'Low', 'Medium', 'High', 'Very high']
PRODUCT_LABEL = {'Chocolate (100g)': 'chocolate bar (100 g)', 'Tomatoes (1kg)': 'kilogram of tomatoes',
                 'Shirt': 't-shirt', 'Jacket': 'jacket', 'Smartphone': 'smartphone', 'Laptop': 'laptop'}
TITLE = 'Consumer choices in Switzerland: price and environmental impact'
CONTEXT = (
    'You take part in an online survey of the Swiss Environmental Panel (wave 14, fielded '
    'December 2024 to February 2025). In this part you compare pairs of products and decide '
    'which one you would buy for yourself or for someone else. Every product offer shows its '
    'price in Swiss francs and its total environmental impact across the whole life cycle, '
    'from production to consumption. Environmental impact is graded from very low to very high. '
    'There is no option to buy neither product: in each pair exactly one of the two is chosen.'
)
MAX_TOKENS = 768  # frozen, identical in all arms
BASIC_FIELDS = {'age_years': 'Age in years', 'education': 'Highest completed education',
                'gender': 'Gender', 'household_income': 'Household income band',
                'country': 'Country of residence'}


def price_text(product, label):
    index = PRICE_ORDER.index(label)
    return f'{PRICE_LEVELS[product][index]:.2f} CHF'


def option_label(product, item):
    return (f'{PRODUCT_LABEL[product]}, price {price_text(product, item["price"])}, '
            f'environmental impact {item["impact"].lower()}')


def questions(person):
    by_product = {}
    for item in person['tasks']:
        by_product.setdefault(item['product'], {}).setdefault(item['round'], []).append(item)
    out = []
    for product in sorted(by_product, key=lambda name: min(by_product[name])):
        for round_number in sorted(by_product[product]):
            offers = sorted(by_product[product][round_number], key=lambda item: item['offer'])
            out.append({'id': f'{product.lower().replace(" ", "-").replace("(100g)", "100g").replace("(1kg)", "1kg")}-r{round_number}',
                        'prompt': 'If you had to choose, which product would you buy?',
                        'options': {f'offer-{item["offer"]}': option_label(product, item) for item in offers}})
    return out


def basic(person):
    background = person['background']
    return {'age_years': None if background['age_years'] is None else str(background['age_years']),
            'education': background['education'], 'gender': background['gender'],
            'household_income': background['income_band'], 'country': background['country']}


def payload(person, arm, donor=None, persona_text=None):
    if arm == 'matraix':
        if not persona_text:
            raise ValueError('The matraix arm needs a frozen native persona')
        return {'title': TITLE, 'context': CONTEXT, 'questions': questions(person),
                'persona_text': persona_text}
    body = {'title': TITLE, 'context': CONTEXT, 'questions': questions(person), 'basic': basic(person)}
    if arm == 'own':
        body['extra'] = {column: ('Unknown' if value is None else str(value))
                         for column, value in person['facts'].items()}
    elif arm == 'other':
        if donor is None:
            raise ValueError('The mismatched arm needs a donor')
        body['extra'] = {column: ('Unknown' if value is None else str(value))
                         for column, value in donor['facts'].items()}
    elif arm != 'basic':
        raise ValueError('Unknown arm')
    return body


def extra_whitelist():
    """Item wording plus its declared scale, so a bare number is never ambiguous."""
    labels = {}
    for column, block, wording in swiss.FACT_ITEMS:
        low, high = swiss.SCALE['dipb'] if block in ('change', 'goals', 'relations', 'knowledge', 'token') \
            else swiss.SCALE[block]
        labels[column] = f'{wording.rstrip(".")} (1 = {low}, 7 = {high})'
    return labels
