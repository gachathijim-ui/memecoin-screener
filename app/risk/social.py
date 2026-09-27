from app.connectors.dexscreener import DexScreenerConnector
from app.connectors.pumpfun import PumpFunConnector
from app.models.report import SocialRisk
from app.models.token import Chain, Socials


async def analyze_social(
    chain: Chain,
    address: str,
    pumpfun: PumpFunConnector,
    dexscreener: DexScreenerConnector,
) -> SocialRisk:
    flags: list = []
    socials = Socials()
    score = 0.0

    if chain == Chain.SOLANA:
        coin = await pumpfun.get_coin(address)
        if coin:
            socials.twitter = coin.get("twitter")
            socials.telegram = coin.get("telegram")
            socials.website = coin.get("website")

    if not any([socials.twitter, socials.telegram, socials.website]):
        pairs = await dexscreener.get_token_pairs(chain.value, address)
        if pairs:
            info = pairs[0].get("info") or {}
            social_list = info.get("socials") or []
            for s in social_list:
                if s.get("type") == "twitter" and not socials.twitter:
                    socials.twitter = s.get("url")
                if s.get("type") == "telegram" and not socials.telegram:
                    socials.telegram = s.get("url")
            websites = info.get("websites") or []
            if websites and not socials.website:
                socials.website = websites[0].get("url")

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
