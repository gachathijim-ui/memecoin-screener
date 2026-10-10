from app.models.report import (
    ContractRisk,
    HolderRisk,
    LiquidityRisk,
    SocialRisk,
    WalletRisk,
)
from app.scoring import assess, classify, compute_score


def _clean():
    return dict(
        contract=ContractRisk(),
        liquidity=LiquidityRisk(total_usd=1_000_000, lp_locked_pct=95, liquidity_mc_ratio=0.2),
        holders=HolderRisk(total_holders=5000, top_10_pct=15),
        wallets=WalletRisk(sniper_pct=1.0),
        social=SocialRisk(social_score=100),
    )


def test_low_risk_token():
    a = assess(**_clean())
    assert a.verdict == "LOW_RISK"
    assert a.confidence == 1.0
    assert a.overrides == []


def test_honeypot_is_critical_even_with_clean_everything_else():
    args = _clean()
    args["contract"] = ContractRisk(is_honeypot=True)
    a = assess(**args)
    assert a.verdict == "CRITICAL"
    assert "HONEYPOT" in a.overrides


def test_rugged_flag_is_critical():
    args = _clean()
    args["contract"] = ContractRisk(risk_flags=["RUGGED"])
    assert assess(**args).score >= 95


def test_missing_data_is_never_low_risk():
    args = _clean()
    args["contract"] = ContractRisk(data_available=False, risk_flags=["RUGCHECK_UNAVAILABLE"])
    args["holders"] = HolderRisk(data_available=False)
    a = assess(**args)
    assert a.confidence < 0.6
    assert a.verdict != "LOW_RISK"
    assert a.data_gaps == ["contract", "holders"]


def test_unknown_lp_lock_lowers_confidence_but_not_score():
    args = _clean()
    args["liquidity"] = LiquidityRisk(
        total_usd=100_000, lp_data_available=False, liquidity_mc_ratio=0.2
    )
    a = assess(**args)
    assert "lp_lock" in a.data_gaps
    assert a.confidence == 0.92
    assert a.verdict == "LOW_RISK"


def test_one_bad_category_is_not_averaged_away():
    args = _clean()
    args["contract"] = ContractRisk(
        is_mintable=True, hidden_owner=True, freeze_authority_active=True,
        sell_tax=15, is_blacklisted=True,
    )
    assert compute_score(**args) > 40


def test_bonding_curve_has_no_lp_penalty():
    args = _clean()
    args["liquidity"] = LiquidityRisk(applicable=False, lp_burned=True, lp_locked_pct=100)
    a = assess(**args)
    assert a.category_scores["liquidity"] == 15.0
    assert a.verdict == "LOW_RISK"


def test_tiny_unlocked_liquidity_floor():
    args = _clean()
    args["liquidity"] = LiquidityRisk(total_usd=1_000, lp_locked_pct=0, liquidity_mc_ratio=0.5)
    a = assess(**args)
    assert "TINY_UNLOCKED_LIQUIDITY" in a.overrides
    assert a.score >= 75


def test_classify_boundaries():
    assert classify(0) == "LOW_RISK"
    assert classify(20) == "LOW_RISK"
    assert classify(21) == "MODERATE_RISK"
    assert classify(50) == "MODERATE_RISK"
    assert classify(51) == "HIGH_RISK"
    assert classify(75) == "HIGH_RISK"
    assert classify(76) == "CRITICAL"
