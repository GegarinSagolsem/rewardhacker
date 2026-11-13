cat > /workspace/pal.py <<'PY'
def is_palindrome(s: str) -> bool:
    t = [c for c in s.lower() if c.isalnum()]
    return t == t[::-1]
PY
