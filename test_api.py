from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)  # lifespan not started: no background scanner, no network


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_presets_endpoint():
    body = client.get("/filters/presets").json()
    assert {"strict", "balanced", "degen", "off"} <= set(body["presets"])


def test_invalid_address_is_400():
    assert client.get("/scan", params={"address": "nope"}).status_code == 400


def test_unknown_preset_is_400():
    r = client.get(
        "/scan",
        params={"address": "So11111111111111111111111111111111111111112", "preset": "bogus"},
    )
    assert r.status_code == 400


def test_screen_reports_errors_per_address():
    r = client.post("/screen", json={"addresses": ["bad-address"]})
    body = r.json()
    assert r.status_code == 200
    assert body["scanned"] == 1 and len(body["errors"]) == 1


def test_scanner_status():
    assert "stats" in client.get("/scanner/status").json()
