cat > /workspace/wc.py <<'PY'
def count_words(text: str) -> int:
    return len(text.split())
PY
