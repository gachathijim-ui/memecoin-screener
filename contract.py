import re
from typing import Optional

from app.connectors.goplus import GoPlusConnector
from app.models.report import ContractRisk
from app.models.token import Chain

_ZERO_ADDRESSES = {
    "",
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
}


def _slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:40]


def _analyze_solana(rc: dict) -> ContractRisk:
    flags: list = []
    mint = bool(rc.get("mintAuthority"))
    freeze = bool(rc.get("freezeAuthority"))
    honeypot = False
    other = 0

    if rc.get("rugged"):
        flags.append("RUGGED")

    for r in rc.get("risks") or []:
        name = (r.get("name") or "").lower()
        level = (r.get("level") or "").lower()
        if "freeze authority" in name:
            freeze = True
        elif "mint authority" in name:
            mint = True
        elif "honeypot" in name:
            honeypot = True
        elif "holder" in name or "liquidity" in name or "lp" in name.split():
            continue  # covered by the holder / liquidity modules
        elif level == "danger":
            other += 1
            if other <= 3:
                flags.append(f"RC_DANGER_{_slug(name)}")

    if freeze:
        flags.append("FREEZE_AUTHORITY_ACTIVE")
    if mint:
        flags.append("MINT_AUTHORITY_ACTIVE")
    if honeypot:
        flags.append("HONEYPOT")

    return ContractRisk(
        is_honeypot=honeypot,
        mint_authority_active=mint,
        freeze_authority_active=freeze,
        ownership_renounced=not mint and not freeze,
        other_danger_count=other,
        risk_flags=flags,
    )


async def _analyze_evm(chain: Chain, address: str, goplus: GoPlusConnector) -> ContractRisk:
    gp = await goplus.token_security(chain.value, address)
    if not gp:
        return ContractRisk(data_available=False, risk_flags=["GOPLUS_NO_DATA"])

    flags: list = []
    buy_tax = float(gp.get("buy_tax") or 0) * 100
    sell_tax = float(gp.get("sell_tax") or 0) * 100
    other = 0

    honeypot = gp.get("is_honeypot") == "1"
    cannot_sell_all = gp.get("cannot_sell_all") == "1"
    mintable = gp.get("is_mintable") == "1"
    hidden_owner = gp.get("hidden_owner") == "1"
    blacklisted = gp.get("is_blacklisted") == "1"

    if honeypot:
        flags.append("HONEYPOT")
    if cannot_sell_all:
        flags.append("CANNOT_SELL_ALL")
    if buy_tax > 10:
        flags.append("HIGH_BUY_TAX")
    if sell_tax > 10:
        flags.append("HIGH_SELL_TAX")
    if mintable:
        flags.append("MINTABLE")
    if hidden_owner:
        flags.append("HIDDEN_OWNER")
    if blacklisted:
        flags.append("BLACKLIST_FUNCTION")

    for key, flag in (
        ("owner_change_balance", "OWNER_CAN_CHANGE_BALANCE"),
        ("can_take_back_ownership", "CAN_TAKE_BACK_OWNERSHIP"),
        ("transfer_pausable", "TRANSFER_PAUSABLE"),
    ):
        if gp.get(key) == "1":
            other += 1
            flags.append(flag)
    if gp.get("is_open_source") == "0":
        other += 1
        flags.append("CLOSED_SOURCE")

    owner = (gp.get("owner_address") or "").lower()

    return ContractRisk(
        is_honeypot=honeypot,
        cannot_sell_all=cannot_sell_all,
        buy_tax=buy_tax,
        sell_tax=sell_tax,
        is_mintable=mintable,
        hidden_owner=hidden_owner,
        is_blacklisted=blacklisted,
        ownership_renounced=owner in _ZERO_ADDRESSES,
        other_danger_count=other,
        lp_holder_count=int(gp.get("lp_holder_count") or 0),
        risk_flags=flags,
    )


async def analyze_contract(
    chain: Chain,
    address: str,
    goplus: GoPlusConnector,
    rugcheck_data: Optional[dict] = None,
) -> ContractRisk:
    """Solana uses the (already fetched) RugCheck report; EVM chains use GoPlus."""
    if chain == Chain.SOLANA:
        if not rugcheck_data:
            return ContractRisk(
                data_available=False, risk_flags=["RUGCHECK_UNAVAILABLE"]
            )
        return _analyze_solana(rugcheck_data)

    try:
        return await _analyze_evm(chain, address, goplus)
    except Exception:
        return ContractRisk(data_available=False, risk_flags=["GOPLUS_UNAVAILABLE"])
