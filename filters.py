"""Filter engine: turns a ScanReport + FilterConfig into a pass/fail FilterResult."""
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.models.filters import Check, FilterConfig, FilterResult
from app.models.report import ScanReport
from app.models.token import Chain


class _NA:
    """Sentinel: rule does not apply to this token (e.g. LP lock on a bonding curve)."""


NA = _NA()
Getter = Callable[[ScanReport], Any]

# --------------------------------------------------------------------------- #
# Presets
# --------------------------------------------------------------------------- #
PRESETS: Dict[str, Dict[str, Any]] = {
    "off": {},
    "strict": {
        "max_risk_score": 30,
        "min_confidence": 0.8,
        "min_age_minutes": 60,
        "min_liquidity_usd": 50_000,
        "min_liquidity_mc_ratio": 0.10,
        "min_lp_locked_pct": 90,
        "min_holders": 500,
        "max_top10_pct": 30,
        "max_top1_pct": 8,
        "max_dev_pct": 3,
        "max_insider_pct": 10,
        "max_sniper_pct": 8,
        "max_bundler_pct": 10,
        "max_fresh_wallet_pct": 25,
        "max_buy_tax": 5,
        "max_sell_tax": 5,
        "require_no_honeypot": True,
        "require_mint_renounced": True,
        "require_freeze_renounced": True,
        "min_social_score": 70,
        "blocked_flags": ["HONEYPOT", "RUGGED", "HIGH_RUG_RATIO", "CANNOT_SELL_ALL"],
        "unknown_policy": "fail",
    },
    "balanced": {
        "max_risk_score": 50,
        "min_confidence": 0.6,
        "min_age_minutes": 5,
        "min_liquidity_usd": 15_000,
        "min_liquidity_mc_ratio": 0.05,
        "min_lp_locked_pct": 50,
        "min_holders": 150,
        "max_top10_pct": 45,
        "max_top1_pct": 15,
        "max_dev_pct": 8,
        "max_insider_pct": 20,
        "max_sniper_pct": 15,
        "max_bundler_pct": 20,
        "max_buy_tax": 10,
        "max_sell_tax": 10,
        "require_no_honeypot": True,
        "require_mint_renounced": True,
        "require_freeze_renounced": True,
        "min_social_score": 30,
        "blocked_flags": ["HONEYPOT", "RUGGED", "CANNOT_SELL_ALL"],
        "unknown_policy": "fail",
    },
    "degen": {
        "max_risk_score": 70,
        "min_confidence": 0.4,
        "min_liquidity_usd": 5_000,
        "min_holders": 50,
        "max_top10_pct": 60,
        "max_top1_pct": 25,
        "max_dev_pct": 15,
        "max_buy_tax": 20,
        "max_sell_tax": 20,
        "require_no_honeypot": True,
        "require_freeze_renounced": True,
        "blocked_flags": ["HONEYPOT", "RUGGED", "CANNOT_SELL_ALL"],
        "unknown_policy": "ignore",
    },
}


def build_config(preset: str, overrides: Optional[Dict[str, Any]] = None) -> FilterConfig:
    key = (preset or "balanced").lower()
    if key not in PRESETS:
        raise ValueError(f"Unknown filter preset {preset!r}. Options: {sorted(PRESETS)}")
    data = {**PRESETS[key], **(overrides or {})}
    name = key if not overrides else f"{key}+overrides"
    return FilterConfig(preset=name, **data)


def merge_config(base: FilterConfig, overrides: Optional[Dict[str, Any]]) -> FilterConfig:
    if not overrides:
        return base
    return FilterConfig(**{**base.model_dump(), **overrides, "preset": f"{base.preset}+overrides"})


# --------------------------------------------------------------------------- #
# Getters: return a value, None (= unknown / data missing) or NA (= not applicable)
# --------------------------------------------------------------------------- #
def _liq(field: str) -> Getter:
    def get(r: ScanReport):
        if not r.liquidity.applicable:
            return NA
        if not r.liquidity.data_available:
            return None
        return getattr(r.liquidity, field)
    return get


def _lp_locked(r: ScanReport):
    l = r.liquidity
    if not l.applicable:
        return NA
    if not l.data_available or not l.lp_data_available:
        return None
    return 100.0 if l.lp_burned else l.lp_locked_pct


def _market(field: str) -> Getter:
    return lambda r: getattr(r.market, field)


def _holders(field: str) -> Getter:
    return lambda r: getattr(r.holders, field) if r.holders.data_available else None


def _wallets(field: str) -> Getter:
    return lambda r: getattr(r.wallets, field) if r.wallets.data_available else None


def _tax(field: str) -> Getter:
    def get(r: ScanReport):
        if r.chain == Chain.SOLANA:
            return NA
        return getattr(r.contract, field) if r.contract.data_available else None
    return get


def _contract_flag(field: str, solana_only: bool = False, evm_field: Optional[str] = None) -> Getter:
    def get(r: ScanReport):
        if solana_only and r.chain != Chain.SOLANA:
            return NA
        if not r.contract.data_available:
            return None
        if r.chain != Chain.SOLANA and evm_field:
            return getattr(r.contract, evm_field)
        return getattr(r.contract, field)
    return get


# (rule/config field, kind, getter)  kind: min | max | false | true
RULES: List[Tuple[str, str, Getter]] = [
    ("max_risk_score", "max", lambda r: r.risk_score),
    ("min_confidence", "min", lambda r: r.confidence),
    ("min_market_cap", "min", _market("market_cap")),
    ("max_market_cap", "max", _market("market_cap")),
    ("min_volume_1h", "min", _market("volume_1h")),
    ("min_volume_24h", "min", _market("volume_24h")),
    ("min_txns_1h", "min", _market("txns_1h")),
    ("min_age_minutes", "min", _market("age_minutes")),
    ("max_age_minutes", "max", _market("age_minutes")),
    ("min_liquidity_usd", "min", _liq("total_usd")),
    ("min_liquidity_mc_ratio", "min", _liq("liquidity_mc_ratio")),
    ("min_lp_locked_pct", "min", _lp_locked),
    ("min_holders", "min", _holders("total_holders")),
    ("max_top10_pct", "max", _holders("top_10_pct")),
    ("max_top1_pct", "max", _holders("top_1_pct")),
    ("max_dev_pct", "max", _holders("dev_pct")),
    ("max_insider_pct", "max", _holders("insider_pct")),
    ("max_sniper_pct", "max", _wallets("sniper_pct")),
    ("max_bundler_pct", "max", _wallets("bundler_pct")),
    ("max_fresh_wallet_pct", "max", _wallets("fresh_wallet_pct")),
    ("max_buy_tax", "max", _tax("buy_tax")),
    ("max_sell_tax", "max", _tax("sell_tax")),
    ("require_no_honeypot", "false", _contract_flag("is_honeypot")),
    ("require_mint_renounced", "false", _contract_flag("mint_authority_active", evm_field="is_mintable")),
    ("require_freeze_renounced", "false", _contract_flag("freeze_authority_active", solana_only=True)),
    ("min_social_score", "min", lambda r: r.social.social_score),
    ("require_twitter", "true", lambda r: bool(r.social.socials.twitter)),
]


def _fmt(v: Any) -> Any:
    return round(v, 2) if isinstance(v, float) else v


def _check_rule(name: str, kind: str, expected: Any, actual: Any) -> Check:
    if actual is NA:
        return Check(rule=name, status="n/a", message="not applicable to this token")
    if actual is None:
        return Check(rule=name, status="unknown", expected=expected, message="data unavailable")

    if kind == "min":
        ok = actual >= expected
        msg = f"{_fmt(actual)} (need >= {expected})"
    elif kind == "max":
        ok = actual <= expected
        msg = f"{_fmt(actual)} (need <= {expected})"
    elif kind == "false":
        ok = not actual
        msg = "must not be active" if actual else "ok"
    else:  # true
        ok = bool(actual)
        msg = "present" if actual else "missing"
    return Check(
        rule=name,
        status="pass" if ok else "fail",
        actual=_fmt(actual),
        expected=expected,
        message=msg,
    )


def evaluate(report: ScanReport, cfg: FilterConfig) -> FilterResult:
    checks: List[Check] = []

    # --- categorical rules -------------------------------------------------
    if cfg.allowed_chains:
        ok = report.chain in cfg.allowed_chains
        checks.append(Check(
            rule="allowed_chains", status="pass" if ok else "fail",
            actual=report.chain.value, expected=[c.value for c in cfg.allowed_chains],
            message="chain allowed" if ok else "chain not allowed",
        ))
    if cfg.allowed_verdicts:
        ok = report.verdict in cfg.allowed_verdicts
        checks.append(Check(
            rule="allowed_verdicts", status="pass" if ok else "fail",
            actual=report.verdict, expected=cfg.allowed_verdicts,
            message=f"verdict {report.verdict}",
        ))
    if cfg.blocked_flags:
        hit = sorted(set(cfg.blocked_flags) & set(report.red_flags))
        checks.append(Check(
            rule="blocked_flags", status="fail" if hit else "pass",
            actual=hit, expected=cfg.blocked_flags,
            message=f"blocked flags present: {', '.join(hit)}" if hit else "no blocked flags",
        ))

    # --- table-driven rules ------------------------------------------------
    for name, kind, getter in RULES:
        expected = getattr(cfg, name)
        if kind in ("false", "true"):
            if not expected:
                continue
        elif expected is None:
            continue
        checks.append(_check_rule(name, kind, expected, getter(report)))

    failed = [c.rule for c in checks if c.status == "fail"]
    unknown = [c.rule for c in checks if c.status == "unknown"]
    passed = not failed and (cfg.unknown_policy == "ignore" or not unknown)

    return FilterResult(
        passed=passed,
        preset=cfg.preset,
        checks=checks,
        failed=failed + ([u for u in unknown] if cfg.unknown_policy == "fail" else []),
        unknown=unknown,
        passed_count=sum(1 for c in checks if c.status == "pass"),
        failed_count=len(failed),
    )
