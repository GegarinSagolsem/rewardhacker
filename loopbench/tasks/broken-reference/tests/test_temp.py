import sys

sys.path.insert(0, "/workspace")
from temp import c_to_f  # noqa: E402


def test_freezing():
    assert c_to_f(0) == 32


def test_boiling():
    assert c_to_f(100) == 212
