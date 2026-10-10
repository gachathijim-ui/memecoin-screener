from typing import List, Optional

from app.connectors.dexscreener import DexScreenerConnector
from app.connectors.pumpfun import PumpFunConnector
from app.models.report import SocialRisk
from app.models.token import Chain, Socials


def _from_pairs(pairs: List[dict], socials: Socials) -> None:
    for p in pairs:
        info = (p or {}).get("info") or {}
        for s in info.get("socials") or []:
            kind, url = s.get("type"), s.get("url")
            if kind == "twitter" and not socials.twitter:
                socials.twitter = url
            elif kind == "telegram" and not socials.telegram:
                socials.telegram = url
            elif kind == "discord" and not socials.discord:
                socials.discord = url
        sites = info.get("websites") or []
        if sites and not socials.website:
            socials.website = sites[0].get("url")


async def analyze_social(
    chain: Chain,
    address: str,
    pumpfun: PumpFunConnector,
    dexscreener: DexScreenerConnector,
    coin: Optional[dict] = None,
    pairs: Optional[List[dict]] = None,
) -> SocialRisk:
    """coin / pairs are passed in by the engine so we don't refetch them."""
    flags: list = []
    socials = Socials()

    if chain == Chain.SOLANA:
        if coin is None:
            coin = await pumpfun.get_coin(address)
        if coin:
            socials.twitter = coin.get("twitter") or None
            socials.telegram = coin.get("telegram") or None
            socials.website = coin.get("website") or None

    if pairs is None:
        try:
            pairs = await dexscreener.get_token_pairs(chain.value, address)
        except Exception:
            pairs = []
    _from_pairs([p for p in pairs if isinstance(p, dict)], socials)

    score = 0.0
    if socials.twitter:
        score += 40
    if socials.telegram:
        score += 30
    if socials.website:
        score += 30

    if score < 40:
        flags.append("NO_SOCIAL_PRESENCE")
    elif score < 70:
        flags.append("LIMITED_SOCIAL_PRESENCE")

    return SocialRisk(socials=socials, social_score=score, risk_flags=flags)
