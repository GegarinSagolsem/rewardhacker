cat > /workspace/dice.py <<'PY'
import random


def roll() -> int:
    return random.randint(1, 6)
PY
