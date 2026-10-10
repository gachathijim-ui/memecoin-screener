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

    resp = await gmgn.rugcheck(chain.value, address)
    rc = resp.get("data") if isinstance(resp, dict) and isinstance(resp.get("data"), dict) else resp

    if not rc:
        return WalletRisk(data_available=False, risk_flags=["WALLET_DATA_UNAVAILABLE"])

    rug_ratio = float(rc.get("rug_ratio") or 0)
    sniper_count = int(rc.get("sniper_count") or 0)
    holder_count = int(rc.get("holder_count") or 0)
    bundler_rate = float(rc.get("bundler_rate") or 0)
    bundler_count = int(rc.get("bundler_count") or 0)

    sniper_pct = (sniper_count / holder_count) * 100 if holder_count else 0.0
    # bundler_rate is a share of supply: 0-1 fraction or already a percentage.
    bundler_pct = bundler_rate * 100 if bundler_rate <= 1 else bundler_rate
    fresh_pct = float(rc.get("fresh_wallet_pct") or 0)
    smart_money = int(rc.get("smart_money_buys") or 0)

    if rug_ratio > 0.7:
        flags.append("HIGH_RUG_RATIO")
    if sniper_pct > 15:
        flags.append("HIGH_SNIPER_CONCENTRATION")
    if bundler_pct > 20 or bundler_count >= 3:
        flags.append("BUNDLERS_DETECTED")
    if fresh_pct > 30:
        flags.append("HIGH_FRESH_WALLET_SHARE")

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
        data_available=True,
        whales=whales,
        bundlers_detected=bundler_count,
        bundler_pct=bundler_pct,
        sniper_pct=sniper_pct,
        fresh_wallet_pct=fresh_pct,
        smart_money_buys=smart_money,
        risk_flags=flags,
    )
