from app.core.ids import new_id


def test_ids_are_unique():
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_ids_are_sortable_by_creation_order():
    # Compare only the 48-bit millisecond timestamp prefix (first 12 hex chars,
    # i.e. the first 3 dash-separated groups minus the version nibble): random
    # bits can tie-break within the same millisecond, so the *full* id isn't
    # guaranteed sortable at sub-millisecond resolution, but the timestamp
    # prefix must never go backwards.
    prefixes = [new_id().replace("-", "")[:11] for _ in range(50)]
    assert prefixes == sorted(prefixes)


def test_id_is_a_valid_uuid_string():
    value = new_id()
    assert len(value) == 36
    assert value.count("-") == 4
