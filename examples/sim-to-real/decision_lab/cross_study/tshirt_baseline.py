"""US T-shirt study: option text and the attribute-only reference features.

Every card in this study is shown to about one respondent, so there is no historical
share to copy. The same-information reference is therefore a conditional logit on the
displayed attributes: origin, material, quality and price. Images were not archived, so
only these文字 attributes are used and the report must say so.
"""
import re

ORIGINS = ['China', 'Pakistan', 'Malaysia', 'Taiwan', 'South Korea', 'Vietnam', 'Philippines',
           'Thailand', 'India']
MATERIALS = ['100% polyester', 'cotton/poly blend', '100% organic cotton', '100% cotton']
QUALITY = ['Poor', 'Fair', 'Good', 'Very good', 'Excellent']


def option_text(origin, material, quality, price):
    return f'Made in: {origin}, material: {material}, quality: {quality}, price: ${price}'


def attributes(label):
    """Fixed-width features: origin dummies, material dummies, quality rank, price."""
    origin = re.search(r'Made in: ([^,]+)', label)
    material = re.search(r'material: ([^,]+)', label)
    quality = re.search(r'quality: ([^,]+)', label)
    price = re.search(r'price: \$([\d.]+)', label)
    if not (origin and material and quality and price):
        raise ValueError('Unreadable T-shirt attributes: ' + label)
    vector = [1.0 if origin.group(1) == level else 0.0 for level in ORIGINS[1:]]
    vector += [1.0 if material.group(1) == level else 0.0 for level in MATERIALS[1:]]
    if quality.group(1) not in QUALITY:
        raise ValueError('Unknown quality label: ' + quality.group(1))
    vector.append(float(QUALITY.index(quality.group(1)) + 1))
    vector.append(float(price.group(1)))
    return vector
