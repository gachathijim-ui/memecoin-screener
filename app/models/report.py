from typing import Any, Dict, List

from pydantic import BaseModel

from .token import Chain, Socials


class ContractRisk(BaseModel):
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
    lp_holder_count: int = 0
    risk_flags: List[str] = []


class LiquidityRisk(BaseModel):
    total_usd: float = 0.0
    lp_locked_pct: float = 0.0
    lp_burned: bool = False
    liquidity_mc_ratio: float = 0.0
    lp_holder_count: int = 0
    risk_flags: List[str] = []


class HolderRisk(BaseModel):
    total_holders: int = 0
    top_10_pct: float = 0.0
    top_1_pct: float = 0.0
    dev_pct: float = 0.0
    insider_pct: float = 0.0
    holder_growth_1h: float = 0.0
    risk_flags: List[str] = []


class WalletRisk(BaseModel):
    whales: List[Dict[str, Any]] = []
    bundlers_detected: int = 0
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
    contract: ContractRisk
    liquidity: LiquidityRisk
    holders: HolderRisk
    wallets: WalletRisk
    social: SocialRisk
    red_flags: List[str] = []
    raw_sources: Dict[str, Any] = {}
