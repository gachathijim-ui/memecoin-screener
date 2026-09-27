from app.connectors.gmgn import GMGNConnector
from app.models.report import WalletRisk
from app.models.token import Chain


async def analyze_wallets(
    chain: Chain,
    address: str,
    gmgn: GMGNConnector,
) -> WalletRisk:
    flags: list = []
    whales: list = []
    bundlers = 0
    sniper_pct = 0.0
    fresh_pct = 0.0
    smart_money = 0

    rc = await gmgn.rugcheck(chain.value, address)

    if not rc:
        return WalletRisk(risk_flags=["WALLET_DATA_UNAVAILABLE"])

    rug_ratio = float(rc.get("rug_ratio") or 0)
    sniper_count = int(rc.get("sniper_count") or 0)
    bundler_rate = float(rc.get("bundler_rate") or 0)
    holder_count = int(rc.get("holder_count") or 1) or 1

    sniper_pct = (sniper_count / holder_count) * 100 if holder_count else 0
    bundlers = int(bundler_rate * 10) if bundler_rate else 0
    fresh_pct = float(rc.get("fresh_wallet_pct") or 0)
    smart_money = int(rc.get("smart_money_buys") or 0)

    if rug_ratio > 0.7:
        flags.append("HIGH_RUG_RATIO")
    if sniper_pct > 15:
        flags.append("HIGH_SNIPER_CONCENTRATION")
    if bundlers >= 3:
        flags.append("BUNDLERS_DETECTED")

    for h in (rc.get("holders") or [])[:10]:
        pct = float(h.get("percent") or 0)
        if pct > 5:
            whales.append(
                {
                    "address": h.get("address"),
                    "balance_pct": pct,
                    "label": h.get("tag", "unknown"),
                }
            )

    return WalletRisk(
        whales=whales,
        bundlers_detected=bundlers,
        sniper_pct=sniper_pct,
        fresh_wallet_pct=fresh_pct,
        smart_money_buys=smart_money,
        risk_flags=flags,
    )
