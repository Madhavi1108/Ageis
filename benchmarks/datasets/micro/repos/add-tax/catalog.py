"""Product catalog -- a distractor for localization."""

ITEMS = {"widget": 9.99, "gadget": 19.99}


def price_of(name):
    return ITEMS.get(name, 0.0)
