import pytest

from app.filters import PRESETS, build_config, evaluate
from app.models.report import ContractRisk, HolderRisk, LiquidityRisk
from app.models.token import Chain
from tests.helpers import make_report


def status(result, rule):
    return next(c.status for c in result.checks if c.rule == rule)


def test_healthy_token_passes_balanced():
    r = evaluate(make_report(), build_config("balanced"))
    assert r.passed, r.failed
    assert r.failed_count == 0


def test_low_liquidity_fails():
    rep = make_report(liquidity=LiquidityRisk(total_usd=5_000, lp_locked_pct=95, liquidity_mc_ratio=0.4))
    r = evaluate(rep, build_config("balanced"))
    assert not r.passed
    assert "min_liquidity_usd" in r.failed


def test_overrides_are_applied():
    r = evaluate(make_report(), build_config("balanced", {"min_liquidity_usd": 500_000}))
    assert "min_liquidity_usd" in r.failed
    assert r.preset == "balanced+overrides"


def test_unknown_data_fails_by_default_and_can_be_ignored():
    rep = make_report(holders=HolderRisk(data_available=False))
    strict_unknown = evaluate(rep, build_config("balanced"))
    assert not strict_unknown.passed
    assert "min_holders" in strict_unknown.unknown

    lenient = evaluate(rep, build_config("balanced", {"unknown_policy": "ignore"}))
    assert lenient.passed
    assert status(lenient, "min_holders") == "unknown"


def test_bonding_curve_skips_liquidity_rules():
    rep = make_report(liquidity=LiquidityRisk(applicable=False, lp_burned=True, lp_locked_pct=100))
    r = evaluate(rep, build_config("balanced"))
    assert status(r, "min_liquidity_usd") == "n/a"
    assert status(r, "min_lp_locked_pct") == "n/a"
    assert r.passed


def test_lp_burned_counts_as_fully_locked():
    rep = make_report(liquidity=LiquidityRisk(
        total_usd=200_000, lp_locked_pct=0, lp_burned=True, liquidity_mc_ratio=0.4))
    assert status(evaluate(rep, build_config("strict")), "min_lp_locked_pct") == "pass"


def test_blocked_flags():
    r = evaluate(make_report(red_flags=["HONEYPOT"]), build_config("balanced"))
    assert "blocked_flags" in r.failed


def test_active_mint_authority_fails_on_solana():
    rep = make_report(contract=ContractRisk(mint_authority_active=True))
    assert "require_mint_renounced" in evaluate(rep, build_config("balanced")).failed


def test_tax_rules_apply_on_evm_only():
    evm = make_report(chain=Chain.ETHEREUM, contract=ContractRisk(buy_tax=25))
    assert "max_buy_tax" in evaluate(evm, build_config("balanced")).failed
    sol = make_report(contract=ContractRisk(buy_tax=25))
    assert status(evaluate(sol, build_config("balanced")), "max_buy_tax") == "n/a"


def test_freeze_rule_is_solana_only():
    evm = make_report(chain=Chain.ETHEREUM)
    assert status(evaluate(evm, build_config("balanced")), "require_freeze_renounced") == "n/a"


def test_allowed_chains():
    cfg = build_config("off", {"allowed_chains": ["base"]})
    assert not evaluate(make_report(), cfg).passed
    assert evaluate(make_report(chain=Chain.BASE), cfg).passed


def test_off_preset_passes_everything():
    rep = make_report(red_flags=["HONEYPOT"], risk_score=99, verdict="CRITICAL")
    assert evaluate(rep, build_config("off")).passed


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        build_config("balanced", {"not_a_real_filter": 1})
    with pytest.raises(ValueError):
        build_config("nope")


def test_all_presets_build():
    for name in PRESETS:
        assert build_config(name).preset == name
