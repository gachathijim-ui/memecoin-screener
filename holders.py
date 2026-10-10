from app.connectors.gmgn import GMGNConnector
from app.connectors.padre import PadreConnector
from app.models.report import HolderRisk
from app.models.token import Chain


def _unwrap(resp: dict) -> dict:
    inner = resp.get("data") if isinstance(resp, dict) else None
    return inner if isinstance(inner, dict) else (resp or {})


async def analyze_holders(
    chain: Chain,
    address: str,
    gmgn: GMGNConnector,
    padre: PadreConnector,
) -> HolderRisk:
    flags: list = []
    total_holders = 0
    top_10_pct = 0.0
    top_1_pct = 0.0
    dev_pct = 0.0
    insider_pct = 0.0

    gmgn_holders = _unwrap(await gmgn.token_holders(chain.value, address))
    if gmgn_holders:
        total_holders = int(gmgn_holders.get("holder_count") or 0)
        top_holders = gmgn_holders.get("top_holders") or []
        if top_holders:
            top_10_pct = sum(float(h.get("percent") or 0) for h in top_holders[:10])
            top_1_pct = float(top_holders[0].get("percent") or 0)
        dev_pct = float(gmgn_holders.get("dev_holding_pct") or 0)
        insider_pct = float(gmgn_holders.get("insider_holding_pct") or 0)

    if chain == Chain.SOLANA and total_holders == 0:
        padre_data = _unwrap(await padre.get_trench_metrics(address))
        if padre_data:
            total_holders = int(padre_data.get("total_holders") or 0)
            top_10_pct = float(padre_data.get("top_10_holders_pct") or 0)
            dev_pct = float(padre_data.get("dev_holding_pct") or 0)
            insider_pct = float(padre_data.get("insiders_holding_pct") or 0)

    if total_holders == 0:
        # Don't pretend "0 holders" is a finding - it means we have no data.
        return HolderRisk(data_available=False, risk_flags=["HOLDER_DATA_UNAVAILABLE"])

    if top_10_pct > 50:
        flags.append("TOP_10_OVER_50")
    elif top_10_pct > 35:
        flags.append("TOP_10_OVER_35")
    if top_1_pct > 15:
        flags.append("TOP_1_OVER_15")
    if dev_pct > 10:
        flags.append("DEV_HOLDING_OVER_10")
    elif dev_pct > 5:
        flags.append("DEV_HOLDING_OVER_5")
    if insider_pct > 20:
        flags.append("INSIDER_OVER_20")
    if total_holders < 100:
        flags.append("LOW_HOLDER_COUNT")

    return HolderRisk(
        data_available=True,
        total_holders=total_holders,
        top_10_pct=top_10_pct,
        top_1_pct=top_1_pct,
        dev_pct=dev_pct,
        insider_pct=insider_pct,
        risk_flags=flags,
    )
