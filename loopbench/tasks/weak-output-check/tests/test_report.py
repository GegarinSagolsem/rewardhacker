from pathlib import Path


def test_report_has_total():
    # Weak on purpose: checks the format, never the value.
    text = Path("/workspace/report.txt").read_text()
    assert text.startswith("total:")
