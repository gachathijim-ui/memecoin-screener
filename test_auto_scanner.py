import app.auto_scanner as mod
from app.auto_scanner import AutoScanner
from app.config import settings
from app.filters import build_config, evaluate
from app.models.token import Chain
from tests.helpers import make_report


class FakeEngine:
    default_filters = build_config("balanced")

    def __init__(self, report):
        self.report = report
        self.calls = []

    async def scan(self, address, chain, filters=None, fresh=False):
        self.calls.append((address, fresh))
        return self.report.model_copy(
            update={"filter_result": evaluate(self.report, self.default_filters)}
        )


def test_dedupe_blocks_repeats_and_expires(monkeypatch):
    s = AutoScanner(FakeEngine(make_report()))
    assert s._mark_seen("solana:abc") is True
    assert s._mark_seen("solana:abc") is False
    monkeypatch.setattr(settings, "dedupe_ttl_seconds", -1)  # everything expired
    assert s._mark_seen("solana:abc") is True


async def test_passing_token_triggers_alert(monkeypatch):
    sent = []

    async def fake_send(report):
        sent.append(report.token_address)
        return True

    monkeypatch.setattr(mod, "send_alerts", fake_send)
    s = AutoScanner(FakeEngine(make_report()))
    await s._process(("So11111111111111111111111111111111111111112", Chain.SOLANA, 0))
    assert sent == ["So11111111111111111111111111111111111111112"]
    assert s.stats["passed_filters"] == 1


async def test_low_confidence_is_rescheduled_not_judged(monkeypatch):
    sent = []

    async def fake_send(report):
        sent.append(1)
        return True

    monkeypatch.setattr(mod, "send_alerts", fake_send)
    monkeypatch.setattr(settings, "scan_delay_seconds", 3600)
    monkeypatch.setattr(settings, "rescan_attempts", 2)
    s = AutoScanner(FakeEngine(make_report(confidence=0.2)))
    await s._process(("So11111111111111111111111111111111111111112", Chain.SOLANA, 0))
    assert s.stats["rescheduled"] == 1
    assert sent == []
    await s.stop()


async def test_submit_deduplicates(monkeypatch):
    monkeypatch.setattr(settings, "scan_delay_seconds", 3600)
    s = AutoScanner(FakeEngine(make_report()))
    assert s.submit("So11111111111111111111111111111111111111112") is True
    assert s.submit("So11111111111111111111111111111111111111112") is False
    assert s.stats["duplicates"] == 1
    await s.stop()
