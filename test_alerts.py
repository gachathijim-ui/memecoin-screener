from app.alerts import alert_kind, format_telegram
from app.filters import build_config, evaluate
from tests.helpers import make_report


def _with_filters(report, preset="balanced"):
    return report.model_copy(update={"filter_result": evaluate(report, build_config(preset))})


def test_alert_modes():
    good = _with_filters(make_report())
    bad = _with_filters(make_report(verdict="CRITICAL", risk_score=95, red_flags=["HONEYPOT"]))
    assert alert_kind(good, "pass") == "PASSED"
    assert alert_kind(bad, "pass") is None
    assert alert_kind(bad, "risky") == "RISK"
    assert alert_kind(good, "risky") is None
    assert alert_kind(bad, "both") == "RISK"
    assert alert_kind(good, "none") is None


def test_telegram_message_is_html_safe():
    rep = _with_filters(make_report(red_flags=["A_B<script>"]))
    text = format_telegram(rep, "PASSED")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
