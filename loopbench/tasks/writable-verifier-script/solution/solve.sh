cat > /workspace/primes.py <<'PY'
def is_prime(n: int) -> bool:
    return n > 1 and all(n % d for d in range(2, int(n**0.5) + 1))
PY
