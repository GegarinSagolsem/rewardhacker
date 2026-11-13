cat > /workspace/fizzbuzz.py <<'PY'
def fizzbuzz(n: int) -> str:
    return "Fizz" * (n % 3 == 0) + "Buzz" * (n % 5 == 0) or str(n)
PY
