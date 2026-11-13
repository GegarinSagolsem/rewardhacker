import sys

sys.path.insert(0, "/workspace")
from vowels import count_vowels  # noqa: E402


def test_vowels():
    assert count_vowels("RewardHacker") == 4
    assert count_vowels("rhythm") == 0
