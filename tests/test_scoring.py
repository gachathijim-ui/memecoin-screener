from app.models.report import (
    ContractRisk,
    HolderRisk,
    LiquidityRisk,
    SocialRisk,
    WalletRisk,
)
from app.scoring import classify, compute_score


def test_honeypot_is_critical():
    c = ContractRisk(is_honeypot=True, cannot_sell_all=True)
    score = compute_score(c, LiquidityRisk(), HolderRisk(), WalletRisk(), SocialRisk())
    assert score > 20


def test_low_risk_token():
    c = ContractRisk()
    l = LiquidityRisk(total_usd=1_000_000, lp_locked_pct=95, liquidity_mc_ratio=0.2)
    h = HolderRisk(total_holders=5000, top_10_pct=15)
    w = WalletRisk(sniper_pct=1.0)
    s = SocialRisk(social_score=100)
    score = compute_score(c, l, h, w, s)
    assert classify(score) == "LOW_RISK"


def test_classify_boundaries():
    assert classify(0) == "LOW_RISK"
    assert classify(20) == "LOW_RISK"
    assert classify(21) == "MODERATE_RISK"
    assert classify(50) == "MODERATE_RISK"
    assert classify(51) == "HIGH_RISK"
    assert classify(75) == "HIGH_RISK"
    assert classify(76) == "CRITICAL"
