import sys

sys.path.insert(0, "/workspace")
from wc import count_words  # noqa: E402


def test_basic():
    assert count_words("hello world") == 2


def test_empty():
    assert count_words("") == 0


def test_mixed_whitespace():
    assert count_words("  a\tb\n c  ") == 3
