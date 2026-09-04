from math_utils import round_half_up


def test_round_half_up_two_point_five():
    assert round_half_up(2.5) == 3


def test_round_half_up_three_point_one():
    assert round_half_up(3.1) == 3
