from typing import Any, Dict, List, Optional

from app.models.report import LiquidityRisk, MarketData


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _extract_lp(rc: Optional[dict]) -> Optional[Dict[str, Any]]:
    """Best-effort LP lock info from a RugCheck report (top-level or per-market)."""
    if not rc:
        return None
    providers = int(_f(rc.get("totalLPProviders") or rc.get("lpHolderCount")))

    if rc.get("lpLockedPct") is not None:
        locked = _f(rc.get("lpLockedPct"))
        return {
            "locked": locked,
            "burned": bool(rc.get("lpBurned")) or locked >= 99.9,
            "providers": providers,
        }

    weighted = 0.0
    weight = 0.0
    plain: List[float] = []
    for m in rc.get("markets") or []:
        lp = (m or {}).get("lp") or {}
        if lp.get("lpLockedPct") is None:
            continue
        pct = _f(lp.get("lpLockedPct"))
        usd = _f(lp.get("lpTotalUSD"))
        plain.append(pct)
        if usd > 0:
            weighted += pct * usd
            weight += usd
    if not plain:
        return None
    locked = weighted / weight if weight > 0 else sum(plain) / len(plain)
    return {"locked": locked, "burned": locked >= 99.9, "providers": providers}


def analyze_liquidity(
    pairs: Optional[list],
    rugcheck_data: Optional[dict] = None,
    coin: Optional[dict] = None,
    market: Optional[MarketData] = None,
) -> LiquidityRisk:
    """
    pairs: None  -> the DexScreener call failed
           []    -> call worked, token has no pairs (yet)
    """
    clean = [p for p in (pairs or []) if isinstance(p, dict)]

    # Still on the pump.fun bonding curve: there is no LP to pull.
    if not clean and coin and not coin.get("complete"):
        return LiquidityRisk(
            applicable=False,
            lp_data_available=True,
            lp_burned=True,
            lp_locked_pct=100.0,
        )

    if not clean:
        flag = "DEX_DATA_UNAVAILABLE" if pairs is None else "NO_PAIRS_FOUND"
        return LiquidityRisk(
            data_available=False, lp_data_available=False, risk_flags=[flag]
        )

    flags: List[str] = []
    total_liq = sum(_f((p.get("liquidity") or {}).get("usd")) for p in clean)

    # Market cap is a per-token number: take it once, never sum across pairs.
    mc = market.market_cap if market and market.market_cap else 0.0
    if not mc:
        mc = max((_f(p.get("marketCap") or p.get("fdv")) for p in clean), default=0.0)
    ratio = (total_liq / mc) if mc > 0 else None

    if total_liq < 10_000:
        flags.append("LIQUIDITY_UNDER_10K")
    elif total_liq < 50_000:
        flags.append("LIQUIDITY_UNDER_50K")

    if ratio is not None:
        if ratio < 0.05:
            flags.append("LIQUIDITY_MC_RATIO_CRITICAL")
        elif ratio < 0.10:
            flags.append("LIQUIDITY_MC_RATIO_LOW")

    lp = _extract_lp(rugcheck_data)
    lp_locked, lp_burned, lp_providers = 0.0, False, 0
    if lp:
        lp_locked, lp_burned, lp_providers = lp["locked"], lp["burned"], lp["providers"]
        if lp_locked < 50 and not lp_burned:
            flags.append("LP_NOT_LOCKED")
        if lp_providers == 1:
            flags.append("SINGLE_LP_HOLDER")

    return LiquidityRisk(
        applicable=True,
        data_available=True,
        lp_data_available=lp is not None,
        total_usd=total_liq,
        lp_locked_pct=lp_locked,
        lp_burned=lp_burned,
        liquidity_mc_ratio=ratio,
        lp_holder_count=lp_providers,
        risk_flags=flags,
    )
