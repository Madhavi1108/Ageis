from calc import safe_add


def test_module_imports():
    import calc

    assert hasattr(calc, "safe_add")


def test_adds():
    assert safe_add(2, 3) == 5
