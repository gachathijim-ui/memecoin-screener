from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Chain(str, Enum):
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BSC = "bsc"
    BASE = "base"
    ARBITRUM = "arbitrum"
    POLYGON = "polygon"


class Socials(BaseModel):
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    website: Optional[str] = None
    discord: Optional[str] = None


class TokenData(BaseModel):
    address: str
    chain: Chain
    name: Optional[str] = None
    symbol: Optional[str] = None
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    liquidity_usd: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_1h: Optional[float] = None
    price_change_24h: Optional[float] = None
    pair_address: Optional[str] = None
    dex_id: Optional[str] = None
    socials: Socials = Socials()
    raw: Dict[str, Any] = {}
