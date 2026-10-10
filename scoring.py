from dataclasses import dataclass, field
from typing import Dict, List

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

# Share of the final score driven by the single worst hard-risk category, so one
# terrible area cannot be averaged away by four fine ones.
WORST_FACTOR_BLEND = 0.40
HARD_CATEGORIES = ("contract", "liquidity", "holders", "wallets")

# Below this confidence a token can never be labelled LOW_RISK ("unknown" != "safe").
MIN_CONFIDENCE_FOR_LOW_RISK = 0.60
LP_GAP_PENALTY = 0.08  # confidence lost when LP lock data is missing


@dataclass
class Assessment:
    score: float
    confidence: float
    verdict: str
    category_scores: Dict[str, float]
    data_gaps: List[str] = field(default_factory=list)
    overrides: List[str] = field(default_factory=list)


def score_contract(c: ContractRisk) -> float:
    if not c.data_available:
        return 0.0
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
    score += min(c.other_danger_count * 10, 20)
    return min(score, 100)


def score_liquidity(l: LiquidityRisk) -> float:
    if not l.data_available:
        return 0.0
    if not l.applicable:
        return 15.0  # bonding curve: no LP rug, but thin and volatile
    score = 0.0
    if l.total_usd < 10_000:
        score += 40
    elif l.total_usd < 50_000:
        score += 20
    if l.lp_data_available:
        if l.lp_locked_pct < 50 and not l.lp_burned:
            score += 25
        if l.lp_holder_count == 1:
            score += 15
    if l.liquidity_mc_ratio is not None:
        if l.liquidity_mc_ratio < 0.05:
            score += 25
        elif l.liquidity_mc_ratio < 0.10:
            score += 10
    return min(score, 100)


def score_holders(h: HolderRisk) -> float:
    if not h.data_available:
        return 0.0
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
    if not w.data_available:
        return 0.0
    score = 0.0
    if w.sniper_pct > 15:
        score += 30
    elif w.sniper_pct > 8:
        score += 15
    if w.bundler_pct > 20 or w.bundlers_detected >= 3:
        score += 25
    elif w.bundler_pct > 5 or w.bundlers_detected >= 1:
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


def _hard_floors(
    contract: ContractRisk, liquidity: LiquidityRisk, holders: HolderRisk
) -> Dict[str, float]:
    """Deal-breakers: minimum final score regardless of how the rest averages."""
    floors: Dict[str, float] = {}
    if "RUGGED" in contract.risk_flags:
        floors["RUGGED"] = 95
    if contract.is_honeypot:
        floors["HONEYPOT"] = 90
    if contract.cannot_sell_all:
        floors["CANNOT_SELL_ALL"] = 85
    if contract.sell_tax >= 50:
        floors["SELL_TAX_50_PLUS"] = 85
    if contract.mint_authority_active and contract.freeze_authority_active:
        floors["MINT_AND_FREEZE_ACTIVE"] = 70
    if holders.data_available and holders.top_1_pct > 50:
        floors["SINGLE_WALLET_OVER_50"] = 80
    if (
        liquidity.applicable
        and liquidity.data_available
        and liquidity.lp_data_available
        and 0 < liquidity.total_usd < 2_000
        and liquidity.lp_locked_pct < 50
        and not liquidity.lp_burned
    ):
        floors["TINY_UNLOCKED_LIQUIDITY"] = 75
    return floors


def assess(
    contract: ContractRisk,
    liquidity: LiquidityRisk,
    holders: HolderRisk,
    wallets: WalletRisk,
    social: SocialRisk,
) -> Assessment:
    parts = {
        "contract": score_contract(contract),
        "liquidity": score_liquidity(liquidity),
        "holders": score_holders(holders),
        "wallets": score_wallets(wallets),
        "social": score_social(social),
    }
    available = {
        "contract": contract.data_available,
        "liquidity": liquidity.data_available,
        "holders": holders.data_available,
        "wallets": wallets.data_available,
        "social": True,
    }

    gaps: List[str] = [k for k in HARD_CATEGORIES if not available[k]]
    confidence = 1.0 - sum(WEIGHTS[k] for k in gaps)
    if liquidity.applicable and liquidity.data_available and not liquidity.lp_data_available:
        gaps.append("lp_lock")
        confidence -= LP_GAP_PENALTY
    confidence = round(max(confidence, 0.0), 2)

    # Renormalise over the categories we actually have data for.
    total_w = sum(WEIGHTS[k] for k in WEIGHTS if available[k])
    weighted = sum(parts[k] * WEIGHTS[k] for k in WEIGHTS if available[k]) / total_w

    live_hard = [parts[k] for k in HARD_CATEGORIES if available[k]]
    worst = max(live_hard) if live_hard else 0.0
    score = (1 - WORST_FACTOR_BLEND) * weighted + WORST_FACTOR_BLEND * worst

    floors = _hard_floors(contract, liquidity, holders)
    if floors:
        score = max(score, max(floors.values()))

    score = round(min(score, 100.0), 2)
    verdict = classify(score)
    if verdict == "LOW_RISK" and confidence < MIN_CONFIDENCE_FOR_LOW_RISK:
        verdict = "MODERATE_RISK"

    return Assessment(
        score=score,
        confidence=confidence,
        verdict=verdict,
        category_scores={k: round(v, 1) for k, v in parts.items()},
        data_gaps=gaps,
        overrides=sorted(floors),
    )


def compute_score(
    contract: ContractRisk,
    liquidity: LiquidityRisk,
    holders: HolderRisk,
    wallets: WalletRisk,
    social: SocialRisk,
) -> float:
    """Backwards-compatible wrapper."""
    return assess(contract, liquidity, holders, wallets, social).score
