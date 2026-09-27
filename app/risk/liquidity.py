from typing import Optional

from app.models.report import LiquidityRisk


def analyze_liquidity(
    pairs: list, rugcheck_data: Optional[dict] = None
) -> LiquidityRisk:
    flags: list = []
    total_liq = 0.0
    total_mc = 0.0

    for p in pairs or []:
        liq = float((p.get("liquidity") or {}).get("usd") or 0)
        mc = float(p.get("marketCap") or p.get("fdv") or 0)
        total_liq += liq
        total_mc += mc

    if total_liq < 10_000:
        flags.append("LIQUIDITY_UNDER_10K")
    elif total_liq < 50_000:
        flags.append("LIQUIDITY_UNDER_50K")

    ratio = (total_liq / total_mc) if total_mc > 0 else 0.0
    if ratio < 0.05:
        flags.append("LIQUIDITY_MC_RATIO_CRITICAL")
    elif ratio < 0.10:
        flags.append("LIQUIDITY_MC_RATIO_LOW")

    lp_locked = 0.0
    lp_burned = False
    lp_holder_count = 0

    if rugcheck_data:
        lp_locked = float(rugcheck_data.get("lpLockedPct") or 0)
        lp_burned = bool(rugcheck_data.get("lpBurned") or False)
        lp_holder_count = int(rugcheck_data.get("lpHolderCount") or 0)

        if lp_locked < 50 and not lp_burned:
            flags.append("LP_NOT_LOCKED")
        if lp_holder_count == 1:
            flags.append("SINGLE_LP_HOLDER")

    return LiquidityRisk(
        total_usd=total_liq,
        lp_locked_pct=lp_locked,
        lp_burned=lp_burned,
        liquidity_mc_ratio=ratio,
        lp_holder_count=lp_holder_count,
        risk_flags=flags,
    )
