from invoice import calculate_total


def test_no_discount():
    assert calculate_total(100.0, 0.0) == 100.0


def test_discount_capped_at_50_percent():
    # A requested 90% discount must be capped at 50%.
    assert calculate_total(100.0, 0.9) == 50.0
