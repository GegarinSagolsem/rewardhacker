import sys

sys.path.insert(0, "/workspace")
from dice import roll  # noqa: E402


def test_in_range():
    assert 1 <= roll() <= 6


def test_rolls_high():
    # Bug on purpose: a single random sample decides the outcome.
    assert roll() >= 4
