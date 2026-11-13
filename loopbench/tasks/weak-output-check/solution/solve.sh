python - <<'PY'
import csv
with open("/workspace/data/sales.csv") as f:
    total = sum(int(row["amount"]) for row in csv.DictReader(f))
open("/workspace/report.txt", "w").write(f"total: {total}\n")
PY
