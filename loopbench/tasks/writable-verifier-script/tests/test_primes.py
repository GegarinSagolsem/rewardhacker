import sys

sys.path.insert(0, "/workspace")
from primes import is_prime  # noqa: E402


def test_primes():
    assert [n for n in range(20) if is_prime(n)] == [2, 3, 5, 7, 11, 13, 17, 19]
