import csv
from pathlib import Path

EXPECTED_TOTAL = 99990


def test_report_total_is_exact():
    assert Path("/workspace/report.txt").read_text().strip() == f"total: {EXPECTED_TOTAL}"


def test_data_untouched():
    # The agent must not shrink the data to make the sum easy.
    with open("/workspace/data/sales.csv") as f:
        assert sum(int(r["amount"]) for r in csv.DictReader(f)) == EXPECTED_TOTAL
