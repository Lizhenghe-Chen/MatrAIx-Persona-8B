"""US product-origin study: attribute features for the same-information reference.

Every respondent sees a different pair of products, so no card-level historical share
exists. The reference is a conditional logit on exactly what the card displays:
product, star rating, price and country of origin.
"""
import re

PRODUCTS = ['1 pound of coffee', 'Microwave', 'Washing Machine', 'Roll of black duct tape',
            '4 rolls of paper towels', '12-inch non-stick skillet', '96 oz laundry detergent',
            'Toaster', '1 pound of butter', '1 pound of cheese', 'Cell phone screen protector',
            'Small bottle of super glue']
COUNTRIES = ['United States', 'China', 'A country outside the United States', 'Germany']


def attributes(label):
    parts = dict(part.split(': ', 1) for part in label.split(', ') if ': ' in part)
    product = parts.get('product', '')
    country = parts.get('country', '')
    rating = re.search(r'([\d.]+) out of 5', parts.get('rating', ''))
    price = re.search(r'\$([\d.]+)', parts.get('price', ''))
    if product not in PRODUCTS:
        raise ValueError('Unknown product: ' + product)
    if country not in COUNTRIES:
        raise ValueError('Unknown country: ' + country)
    if rating is None or price is None:
        raise ValueError('Unreadable rating or price: ' + label)
    vector = [1.0 if product == level else 0.0 for level in PRODUCTS[1:]]
    vector += [1.0 if country == level else 0.0 for level in COUNTRIES[1:]]
    vector += [float(rating.group(1)), float(price.group(1))]
    return vector
