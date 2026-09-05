"""Unit tests for app/services/tasks.py::compute_idempotency_key.

docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14: idempotency key = hash(repo,
normalized_text), used for duplicate detection.
"""

from __future__ import annotations

from app.services.tasks import compute_idempotency_key, normalize_text

BIG = 50_000


def test_key_is_stable_for_the_same_inputs():
    a = compute_idempotency_key("repo-1", "fix the bug")
    b = compute_idempotency_key("repo-1", "fix the bug")
    assert a == b


def test_key_is_64_hex_chars():
    key = compute_idempotency_key("repo-1", "anything")
    assert len(key) == 64
    int(key, 16)  # parses as hex


def test_key_is_repository_scoped():
    a = compute_idempotency_key("repo-1", "same text")
    b = compute_idempotency_key("repo-2", "same text")
    assert a != b


def test_key_changes_with_text():
    a = compute_idempotency_key("repo-1", "text one")
    b = compute_idempotency_key("repo-1", "text two")
    assert a != b


def test_key_is_normalization_invariant():
    # Cosmetic differences that normalization removes must not change the key.
    text_a = normalize_text("Fix the bug\r\n\r\n", max_bytes=BIG).text
    text_b = normalize_text("   Fix the bug   \n", max_bytes=BIG).text
    assert text_a == text_b
    assert compute_idempotency_key("r", text_a) == compute_idempotency_key("r", text_b)


def test_no_delimiter_collision_between_repo_and_text():
    # A naive "repo" + "text" concat would collide these; the NUL separator must not.
    a = compute_idempotency_key("ab", "cd")
    b = compute_idempotency_key("a", "bcd")
    assert a != b
