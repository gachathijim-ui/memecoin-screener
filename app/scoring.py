from app.models.report import (
    ContractRisk,
    HolderRisk,
    LiquidityRisk,
    SocialRisk,
    WalletRisk,
)

WEIGHTS = {
    "contract": 0.30,
    "liquidity": 0.25,
    "holders": 0.20,
    "wallets": 0.15,
    "social": 0.10,
}


def score_contract(c: ContractRisk) -> float:
    score = 0.0
    if c.is_honeypot:
        score += 50
    if c.cannot_sell_all:
        score += 30
    if c.buy_tax > 10:
        score += 15
    if c.sell_tax > 10:
        score += 20
    if c.is_mintable:
        score += 15
    if c.mint_authority_active:
        score += 10
    if c.freeze_authority_active:
        score += 20
    if c.hidden_owner:
        score += 15
    if c.is_blacklisted:
        score += 10
    return min(score, 100)


def score_liquidity(l: LiquidityRisk) -> float:
    score = 0.0
    if l.total_usd < 10_000:
        score += 40
    elif l.total_usd < 50_000:
        score += 20
    if l.lp_locked_pct < 50 and not l.lp_burned:
        score += 25
    if l.liquidity_mc_ratio < 0.05:
        score += 25
    elif l.liquidity_mc_ratio < 0.10:
        score += 10
    if l.lp_holder_count == 1:
        score += 15
    return min(score, 100)


def score_holders(h: HolderRisk) -> float:
    score = 0.0
    if h.top_10_pct > 50:
        score += 30
    elif h.top_10_pct > 35:
        score += 15
    if h.top_1_pct > 15:
        score += 20
    if h.dev_pct > 10:
        score += 25
    elif h.dev_pct > 5:
        score += 10
    if h.insider_pct > 20:
        score += 20
    if h.total_holders < 100:
        score += 15
    return min(score, 100)


def score_wallets(w: WalletRisk) -> float:
    score = 0.0
    if w.sniper_pct > 15:
        score += 30
    elif w.sniper_pct > 8:
        score += 15
    if w.bundlers_detected >= 3:
        score += 25
    elif w.bundlers_detected >= 1:
        score += 10
    if w.fresh_wallet_pct > 30:
        score += 15
    return min(score, 100)


def score_social(s: SocialRisk) -> float:
    return max(0.0, 100 - s.social_score)


def classify(score: float) -> str:
    if score <= 20:
        return "LOW_RISK"
    if score <= 50:
        return "MODERATE_RISK"
    if score <= 75:
        return "HIGH_RISK"
    return "CRITICAL"


def compute_score(
    contract: ContractRisk,
    liquidity: LiquidityRisk,
    holders: HolderRisk,
    wallets: WalletRisk,
    social: SocialRisk,
) -> float:
    total = (
        score_contract(contract) * WEIGHTS["contract"]
        + score_liquidity(liquidity) * WEIGHTS["liquidity"]
        + score_holders(holders) * WEIGHTS["holders"]
        + score_wallets(wallets) * WEIGHTS["wallets"]
        + score_social(social) * WEIGHTS["social"]
    )
    return round(total, 2)
