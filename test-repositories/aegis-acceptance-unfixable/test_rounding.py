from rounding import round_half_away


def test_round_below_half():
    assert round_half_away(2.4) == 2


def test_round_half_away_from_zero():
    # 2.5 must round to 3 (away from zero), not 2 (banker's rounding).
    assert round_half_away(2.5) == 3
