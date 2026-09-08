from invoice import calculate_total


def test_no_discount():
    assert calculate_total(100.0, 0.0) == 100.0


def test_cap_at_half():
    # a 90% discount must be charged as a 50% discount
    assert calculate_total(100.0, 0.9) == 50.0
