cat > /workspace/vowels.py <<'PY'
def count_vowels(s: str) -> int:
    return sum(c in "aeiou" for c in s.lower())
PY
