from stats import mean


def test_mean_basic():
    assert mean([2, 4]) == 3.0


def test_mean_empty():
    assert mean([]) == 0.0
