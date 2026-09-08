from order import order_total


def test_no_items():
    assert order_total(0) == 0


def test_total_includes_tax():
    assert order_total(100) == 110
