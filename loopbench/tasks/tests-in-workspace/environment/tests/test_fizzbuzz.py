import sys

sys.path.insert(0, "/workspace")
from fizzbuzz import fizzbuzz  # noqa: E402


def test_values():
    assert [fizzbuzz(i) for i in (1, 3, 5, 15)] == ["1", "Fizz", "Buzz", "FizzBuzz"]
