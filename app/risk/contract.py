from app.connectors.goplus import GoPlusConnector
from app.connectors.rugcheck import RugCheckConnector
from app.models.report import ContractRisk
from app.models.token import Chain


async def analyze_contract(
    chain: Chain,
    address: str,
    goplus: GoPlusConnector,
    rugcheck: RugCheckConnector,
) -> ContractRisk:
    flags: list = []

    if chain == Chain.SOLANA:
        try:
            rc = await rugcheck.scan_token(address)
            risks = rc.get("risks", []) if isinstance(rc, dict) else []

            mint_active = False
            freeze_active = False
            honeypot = False

            for r in risks:
                name = (r.get("name") or "").lower()
                if "freeze authority" in name:
                    flags.append("FREEZE_AUTHORITY_ACTIVE")
                    freeze_active = True
                if "mint authority" in name:
                    flags.append("MINT_AUTHORITY_ACTIVE")
                    mint_active = True
                if "honeypot" in name:
                    flags.append("HONEYPOT")
                    honeypot = True
                if "low liquidity" in name:
                    flags.append("LOW_LIQUIDITY")

            return ContractRisk(
                is_honeypot=honeypot,
                mint_authority_active=mint_active,
                freeze_authority_active=freeze_active,
                lp_holder_count=rc.get("totalHolders", 0) if isinstance(rc, dict) else 0,
                risk_flags=flags,
            )
        except Exception:
            return ContractRisk(risk_flags=["RUGCHECK_UNAVAILABLE"])

    try:
        gp = await goplus.token_security(chain.value, address)
        if not gp:
            return ContractRisk(risk_flags=["GOPLUS_NO_DATA"])

        buy_tax = float(gp.get("buy_tax") or 0) * 100
        sell_tax = float(gp.get("sell_tax") or 0) * 100

        if gp.get("is_honeypot") == "1":
            flags.append("HONEYPOT")
        if gp.get("cannot_sell_all") == "1":
            flags.append("CANNOT_SELL_ALL")
        if buy_tax > 10:
            flags.append("HIGH_BUY_TAX")
        if sell_tax > 10:
            flags.append("HIGH_SELL_TAX")
        if gp.get("is_mintable") == "1":
            flags.append("MINTABLE")
        if gp.get("hidden_owner") == "1":
            flags.append("HIDDEN_OWNER")
        if gp.get("is_blacklisted") == "1":
            flags.append("BLACKLIST_FUNCTION")

        return ContractRisk(
            is_honeypot=gp.get("is_honeypot") == "1",
            cannot_sell_all=gp.get("cannot_sell_all") == "1",
            buy_tax=buy_tax,
            sell_tax=sell_tax,
            is_mintable=gp.get("is_mintable") == "1",
            hidden_owner=gp.get("hidden_owner") == "1",
            is_blacklisted=gp.get("is_blacklisted") == "1",
            lp_holder_count=int(gp.get("lp_holder_count") or 0),
            risk_flags=flags,
        )
    except Exception:
        return ContractRisk(risk_flags=["GOPLUS_UNAVAILABLE"])
