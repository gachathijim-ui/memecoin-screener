import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from app.config import settings
from app.connectors.dexscreener import DexScreenerConnector
from app.connectors.gmgn import GMGNConnector
from app.connectors.goplus import GoPlusConnector
from app.connectors.helius import HeliusConnector
from app.connectors.padre import PadreConnector
from app.connectors.pumpfun import PumpFunConnector
from app.connectors.rugcheck import RugCheckConnector
from app.filters import build_config, evaluate
from app.models.filters import FilterConfig
from app.models.report import (
    ContractRisk,
    HolderRisk,
    ScanReport,
    SocialRisk,
    WalletRisk,
)
from app.models.token import Chain
from app.risk.contract import analyze_contract
from app.risk.holders import analyze_holders
from app.risk.liquidity import analyze_liquidity
from app.risk.market import analyze_market
from app.risk.social import analyze_social
from app.risk.wallets import analyze_wallets
from app.scoring import assess
from app.utils import get_logger, validate_address

logger = get_logger(__name__)


async def _none():
    return None


class RiskEngine:
    def __init__(self, filters: Optional[FilterConfig] = None) -> None:
        self.dexscreener = DexScreenerConnector()
        self.goplus = GoPlusConnector()
        self.rugcheck = RugCheckConnector()
        self.gmgn = GMGNConnector()
        self.pumpfun = PumpFunConnector()
        self.padre = PadreConnector()
        self.helius = HeliusConnector()

        self.default_filters = filters or build_config(
            settings.filter_preset, settings.filter_overrides()
        )
        self._cache: Dict[str, Tuple[float, ScanReport]] = {}
        self._inflight: Dict[str, "asyncio.Future[ScanReport]"] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def scan(
        self,
        token_address: str,
        chain: Chain,
        filters: Optional[FilterConfig] = None,
        fresh: bool = False,
    ) -> ScanReport:
        """Analyse a token and run it through the filters.

        Raises ValueError for malformed addresses. Data-source failures never
        raise; they lower the report's confidence instead.
        """
        address = validate_address(chain, token_address)
        base = await self._base_report(address, chain, fresh)
        cfg = filters or self.default_filters
        return base.model_copy(update={"filter_result": evaluate(base, cfg)})

    async def close(self) -> None:
        for c in (
            self.dexscreener, self.goplus, self.rugcheck, self.gmgn,
            self.pumpfun, self.padre, self.helius,
        ):
            await c.close()

    # ------------------------------------------------------------------ #
    # Caching / de-duplication of concurrent scans
    # ------------------------------------------------------------------ #
    async def _base_report(self, address: str, chain: Chain, fresh: bool) -> ScanReport:
        key = f"{chain.value}:{address}"
        now = time.monotonic()

        if not fresh:
            hit = self._cache.get(key)
            if hit and now - hit[0] < settings.scan_cache_ttl_seconds:
                return hit[1]

        fut = self._inflight.get(key)
        if fut is None:
            fut = asyncio.ensure_future(self._analyze(address, chain))
            self._inflight[key] = fut
            fut.add_done_callback(lambda _f, k=key: self._inflight.pop(k, None))

        report = await asyncio.shield(fut)
        self._cache[key] = (time.monotonic(), report)
        if len(self._cache) > 2000:
            cutoff = time.monotonic() - settings.scan_cache_ttl_seconds
            self._cache = {k: v for k, v in self._cache.items() if v[0] >= cutoff}
        return report

    # ------------------------------------------------------------------ #
    # Core analysis
    # ------------------------------------------------------------------ #
    async def _guard(self, label: str, coro):
        """Run one data source with a timeout; None means 'failed'."""
        try:
            return await asyncio.wait_for(coro, settings.module_timeout_seconds)
        except Exception as e:  # noqa: BLE001 - any source failure is non-fatal
            logger.warning("%s failed: %s", label, e)
            return None

    async def _analyze(self, address: str, chain: Chain) -> ScanReport:
        is_sol = chain == Chain.SOLANA

        # 1. Raw data, fetched once and shared by every module.
        pairs, rc, coin = await asyncio.gather(
            self._guard("dexscreener", self.dexscreener.get_token_pairs(chain.value, address)),
            self._guard("rugcheck", self.rugcheck.scan_token(address)) if is_sol else _none(),
            self._guard("pumpfun", self.pumpfun.get_coin(address)) if is_sol else _none(),
        )
        rc = rc or None
        coin = coin or None

        market = analyze_market(pairs, coin)
        liquidity = analyze_liquidity(pairs, rc, coin, market)

        # 2. Independent risk modules in parallel.
        contract, holders, wallets, social = await asyncio.gather(
            self._guard("contract", analyze_contract(chain, address, self.goplus, rc)),
            self._guard("holders", analyze_holders(chain, address, self.gmgn, self.padre)),
            self._guard("wallets", analyze_wallets(chain, address, self.gmgn)),
            self._guard(
                "social",
                analyze_social(chain, address, self.pumpfun, self.dexscreener, coin, pairs or []),
            ),
        )

        # 3. A crashed module is "unknown", never "safe".
        if contract is None:
            contract = ContractRisk(data_available=False, risk_flags=["CONTRACT_MODULE_FAILED"])
        if holders is None:
            holders = HolderRisk(data_available=False, risk_flags=["HOLDER_MODULE_FAILED"])
        if wallets is None:
            wallets = WalletRisk(data_available=False, risk_flags=["WALLET_MODULE_FAILED"])
        if social is None:
            social = SocialRisk(risk_flags=["SOCIAL_MODULE_FAILED"])

        # 4. Score.
        a = assess(contract, liquidity, holders, wallets, social)

        flags = (
            contract.risk_flags
            + liquidity.risk_flags
            + holders.risk_flags
            + wallets.risk_flags
            + social.risk_flags
            + a.overrides
        )
        red_flags = list(dict.fromkeys(flags))  # de-dupe, keep order

        return ScanReport(
            token_address=address,
            chain=chain,
            timestamp=datetime.now(timezone.utc).isoformat(),
            risk_score=a.score,
            verdict=a.verdict,
            confidence=a.confidence,
            data_gaps=a.data_gaps,
            score_breakdown=a.category_scores,
            overrides=a.overrides,
            market=market,
            contract=contract,
            liquidity=liquidity,
            holders=holders,
            wallets=wallets,
            social=social,
            red_flags=red_flags,
            raw_sources={
                "dexscreener_pairs": len(pairs or []),
                "dexscreener_ok": pairs is not None,
                "rugcheck_ok": rc is not None,
                "pumpfun_ok": coin is not None,
            },
        )
