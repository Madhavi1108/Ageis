from config import parse_port


def test_numeric():
    assert parse_port("9090") == 9090


def test_empty_default():
    assert parse_port("") == 8080
