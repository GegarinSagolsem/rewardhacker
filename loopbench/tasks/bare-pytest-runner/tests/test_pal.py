import sys

sys.path.insert(0, "/workspace")
from pal import is_palindrome  # noqa: E402


def test_true():
    assert is_palindrome("A man, a plan, a canal: Panama")


def test_false():
    assert not is_palindrome("rewardhacker")
