from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .filters import FilterResult
from .token import Chain, Socials


class MarketData(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    stage: str = "unknown"  # dex | bonding_curve | migrating | unknown
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    volume_1h: Optional[float] = None
    volume_24h: Optional[float] = None
    price_change_1h: Optional[float] = None
    price_change_24h: Optional[float] = None
    txns_1h: Optional[int] = None
    age_minutes: Optional[float] = None
    dex_id: Optional[str] = None
    pair_address: Optional[str] = None
    pair_count: int = 0


class ContractRisk(BaseModel):
    data_available: bool = True
    is_honeypot: bool = False
    cannot_sell_all: bool = False
    buy_tax: float = 0.0
    sell_tax: float = 0.0
    mint_authority_active: bool = False
    freeze_authority_active: bool = False
    ownership_renounced: bool = False
    is_mintable: bool = False
    hidden_owner: bool = False
    is_blacklisted: bool = False
    other_danger_count: int = 0
    lp_holder_count: int = 0
    risk_flags: List[str] = []


class LiquidityRisk(BaseModel):
    applicable: bool = True       # False while on a bonding curve (no LP to rug)
    data_available: bool = True   # False if no pair data could be obtained
    lp_data_available: bool = True
    total_usd: float = 0.0
    lp_locked_pct: float = 0.0
    lp_burned: bool = False
    liquidity_mc_ratio: Optional[float] = None
    lp_holder_count: int = 0
    risk_flags: List[str] = []


class HolderRisk(BaseModel):
    data_available: bool = True
    total_holders: int = 0
    top_10_pct: float = 0.0
    top_1_pct: float = 0.0
    dev_pct: float = 0.0
    insider_pct: float = 0.0
    holder_growth_1h: float = 0.0
    risk_flags: List[str] = []


class WalletRisk(BaseModel):
    data_available: bool = True
    whales: List[Dict[str, Any]] = []
    bundlers_detected: int = 0
    bundler_pct: float = 0.0
    sniper_pct: float = 0.0
    fresh_wallet_pct: float = 0.0
    smart_money_buys: int = 0
    risk_flags: List[str] = []


class SocialRisk(BaseModel):
    socials: Socials = Socials()
    social_score: float = 0.0
    risk_flags: List[str] = []


class ScanReport(BaseModel):
    token_address: str
    chain: Chain
    timestamp: str
    risk_score: float
    verdict: str
    confidence: float = 1.0
    data_gaps: List[str] = []
    score_breakdown: Dict[str, float] = {}
    overrides: List[str] = []
    market: MarketData = MarketData()
    contract: ContractRisk
    liquidity: LiquidityRisk
    holders: HolderRisk
    wallets: WalletRisk
    social: SocialRisk
    red_flags: List[str] = []
    filter_result: Optional[FilterResult] = None
    raw_sources: Dict[str, Any] = {}
