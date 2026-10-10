import time
from typing import Iterable, List, Optional

from app.models.report import MarketData


def _num(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _sum(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def analyze_market(
    pairs: Optional[List[dict]],
    coin: Optional[dict] = None,
    now: Optional[float] = None,
) -> MarketData:
    """Build price / volume / age metrics from DexScreener pairs (+ pump.fun coin)."""
    now = now or time.time()
    m = MarketData()
    clean = [p for p in (pairs or []) if isinstance(p, dict)]
    created_ms: List[float] = []

    if clean:
        primary = max(
            clean, key=lambda p: _num((p.get("liquidity") or {}).get("usd")) or 0.0
        )
        base = primary.get("baseToken") or {}
        m.name = base.get("name")
        m.symbol = base.get("symbol")
        m.price_usd = _num(primary.get("priceUsd"))
        caps = [_num(p.get("marketCap")) or _num(p.get("fdv")) for p in clean]
        caps = [c for c in caps if c]
        m.market_cap = max(caps) if caps else None
        m.fdv = _num(primary.get("fdv"))
        m.volume_1h = _sum(_num((p.get("volume") or {}).get("h1")) for p in clean)
        m.volume_24h = _sum(_num((p.get("volume") or {}).get("h24")) for p in clean)
        pc = primary.get("priceChange") or {}
        m.price_change_1h = _num(pc.get("h1"))
        m.price_change_24h = _num(pc.get("h24"))

        tx_total = 0
        tx_seen = False
        for p in clean:
            h1 = (p.get("txns") or {}).get("h1")
            if isinstance(h1, dict):
                tx_seen = True
                tx_total += int(h1.get("buys") or 0) + int(h1.get("sells") or 0)
        m.txns_1h = tx_total if tx_seen else None

        created_ms += [c for c in (_num(p.get("pairCreatedAt")) for p in clean) if c]
        m.dex_id = primary.get("dexId")
        m.pair_address = primary.get("pairAddress")
        m.pair_count = len(clean)
        m.stage = "dex"

    if coin:
        m.name = m.name or coin.get("name")
        m.symbol = m.symbol or coin.get("symbol")
        if m.market_cap is None:
            m.market_cap = _num(coin.get("usd_market_cap"))
        ts = _num(coin.get("created_timestamp"))
        if ts:
            created_ms.append(ts)
        if not clean:
            m.stage = "migrating" if coin.get("complete") else "bonding_curve"

    if created_ms:
        m.age_minutes = max(0.0, (now * 1000 - min(created_ms)) / 60000)
    return m
