import asyncio
from datetime import datetime, timezone

from app.connectors.dexscreener import DexScreenerConnector
from app.connectors.gmgn import GMGNConnector
from app.connectors.goplus import GoPlusConnector
from app.connectors.helius import HeliusConnector
from app.connectors.padre import PadreConnector
from app.connectors.pumpfun import PumpFunConnector
from app.connectors.rugcheck import RugCheckConnector
from app.models.report import (
    ContractRisk,
    HolderRisk,
    LiquidityRisk,
    ScanReport,
    SocialRisk,
    WalletRisk,
)
from app.models.token import Chain
from app.risk.contract import analyze_contract
from app.risk.holders import analyze_holders
from app.risk.liquidity import analyze_liquidity
from app.risk.social import analyze_social
from app.risk.wallets import analyze_wallets
from app.scoring import classify, compute_score
from app.utils import get_logger

logger = get_logger(__name__)


async def _noop() -> None:
    return None


class RiskEngine:
    def __init__(self) -> None:
        self.dexscreener = DexScreenerConnector()
        self.goplus = GoPlusConnector()
        self.rugcheck = RugCheckConnector()
        self.gmgn = GMGNConnector()
        self.pumpfun = PumpFunConnector()
        self.padre = PadreConnector()
        self.helius = HeliusConnector()

    async def scan(self, token_address: str, chain: Chain) -> ScanReport:
        # 1. Fetch market + on-chain data in parallel
        dexscreener_task = self.dexscreener.get_token_pairs(
            chain.value, token_address
        )
        rugcheck_task = (
            self.rugcheck.scan_token(token_address)
            if chain == Chain.SOLANA
            else _noop()
        )

        dex_result, rc_result = await asyncio.gather(
            dexscreener_task,
            rugcheck_task,
            return_exceptions=True,
        )

        pairs = [] if isinstance(dex_result, BaseException) else (dex_result or [])
        rugcheck_data = (
            {} if isinstance(rc_result, BaseException) else (rc_result or {})
        )

        # 2. Liquidity analysis is synchronous — run it directly
        liquidity_risk = analyze_liquidity(pairs, rugcheck_data)

        # 3. Async risk modules run in parallel
        results = await asyncio.gather(
            analyze_contract(chain, token_address, self.goplus, self.rugcheck),
            analyze_holders(chain, token_address, self.gmgn, self.padre),
            analyze_wallets(chain, token_address, self.gmgn),
            analyze_social(chain, token_address, self.pumpfun, self.dexscreener),
            return_exceptions=True,
        )

        contract_risk = self._coerce(results[0], ContractRisk)
        holder_risk = self._coerce(results[1], HolderRisk)
        wallet_risk = self._coerce(results[2], WalletRisk)
        social_risk = self._coerce(results[3], SocialRisk)

        # 4. Composite score
        score = compute_score(
            contract_risk,
            liquidity_risk,
            holder_risk,
            wallet_risk,
            social_risk,
        )
        verdict = classify(score)

        # 5. Collect red flags
        red_flags = (
            contract_risk.risk_flags
            + liquidity_risk.risk_flags
            + holder_risk.risk_flags
            + wallet_risk.risk_flags
            + social_risk.risk_flags
        )

        return ScanReport(
            token_address=token_address,
            chain=chain,
            timestamp=datetime.now(timezone.utc).isoformat(),
            risk_score=score,
            verdict=verdict,
            contract=contract_risk,
            liquidity=liquidity_risk,
            holders=holder_risk,
            wallets=wallet_risk,
            social=social_risk,
            red_flags=red_flags,
            raw_sources={
                "dexscreener_pairs": len(pairs),
                "rugcheck_available": bool(rugcheck_data),
            },
        )

    @staticmethod
    def _coerce(value, model_cls):
        if isinstance(value, BaseException) or value is None:
            logger.warning("Risk module failed: %s", value)
            return model_cls()
        return value

    async def close(self) -> None:
        await self.dexscreener.close()
        await self.goplus.close()
        await self.rugcheck.close()
        await self.gmgn.close()
        await self.pumpfun.close()
        await self.padre.close()
        await self.helius.close()