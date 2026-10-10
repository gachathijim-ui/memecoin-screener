from app.models.report import (
    ContractRisk,
    HolderRisk,
    LiquidityRisk,
    MarketData,
    ScanReport,
    SocialRisk,
    WalletRisk,
)
from app.models.token import Chain, Socials


def make_report(chain: Chain = Chain.SOLANA, **overrides) -> ScanReport:
    """A healthy token that passes the 'balanced' preset; override pieces per test."""
    data = dict(
        token_address="So11111111111111111111111111111111111111112",
        chain=chain,
        timestamp="2026-01-01T00:00:00+00:00",
        risk_score=10.0,
        verdict="LOW_RISK",
        confidence=1.0,
        market=MarketData(
            symbol="TEST", name="Test Coin", stage="dex", market_cap=500_000,
            volume_1h=40_000, volume_24h=300_000, txns_1h=400, age_minutes=120,
        ),
        contract=ContractRisk(),
        liquidity=LiquidityRisk(
            total_usd=200_000, lp_locked_pct=95, liquidity_mc_ratio=0.4,
        ),
        holders=HolderRisk(
            total_holders=2000, top_10_pct=20, top_1_pct=5, dev_pct=1, insider_pct=2,
        ),
        wallets=WalletRisk(sniper_pct=3, bundler_pct=2, fresh_wallet_pct=10),
        social=SocialRisk(
            socials=Socials(twitter="https://x.com/t", telegram="https://t.me/t"),
            social_score=70,
        ),
        red_flags=[],
    )
    data.update(overrides)
    return ScanReport(**data)
