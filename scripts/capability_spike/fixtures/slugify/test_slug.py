from slug import slugify


def test_simple_title():
    assert slugify("Hello World") == "hello-world"


def test_strips_punctuation():
    assert slugify("Wait, what?!") == "wait-what"
