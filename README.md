# Memecoin Screener v2

Multi-chain memecoin rug-pull screener: **scan -> score -> filter -> alert**.

## Quick start

    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env        # add Telegram / Discord details
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Docs: http://127.0.0.1:8000/docs

## How a token is judged

1. **Data**: DexScreener, RugCheck / GoPlus, GMGN / Padre, pump.fun are fetched once and shared.
2. **Score** (`app/scoring.py`): weighted category scores, a worst-category blend, and hard
   floors (honeypot, rugged, can't sell, mint+freeze, single wallet >50%, tiny unlocked LP).
3. **Confidence**: drops when a source is missing. Unknown is never reported as safe.
4. **Filters** (`app/filters.py`): every rule returns pass / fail / unknown / n-a with the
   actual value, so you can see exactly why a token was rejected.
5. **Alert**: according to `ALERT_MODE` (`pass`, `risky`, `both`, `none`).

## Filters

Presets: `strict`, `balanced` (default), `degen`, `off`. See `GET /filters/presets`.

Override any rule:

    FILTER_OVERRIDES_JSON={"min_liquidity_usd": 25000, "max_top10_pct": 40}

    curl -X POST localhost:8000/scan -H 'content-type: application/json' \
      -d '{"address":"<MINT>","preset":"strict","filters":{"min_holders":1000}}'

    curl -X POST localhost:8000/screen -H 'content-type: application/json' \
      -d '{"addresses":["<MINT1>","<MINT2>"],"preset":"balanced"}'   # returns only passers

    python cli.py <MINT1> <MINT2> --preset strict --only-passed
    python cli.py <MINT> --set min_liquidity_usd=25000 --set max_top10_pct=40

Available rules: `max_risk_score`, `min_confidence`, `min/max_market_cap`, `min_volume_1h`,
`min_volume_24h`, `min_txns_1h`, `min/max_age_minutes`, `min_liquidity_usd`,
`min_liquidity_mc_ratio`, `min_lp_locked_pct`, `min_holders`, `max_top10_pct`, `max_top1_pct`,
`max_dev_pct`, `max_insider_pct`, `max_sniper_pct`, `max_bundler_pct`, `max_fresh_wallet_pct`,
`max_buy_tax`, `max_sell_tax`, `require_no_honeypot`, `require_mint_renounced`,
`require_freeze_renounced`, `min_social_score`, `require_twitter`, `allowed_chains`,
`allowed_verdicts`, `blocked_flags`, `unknown_policy` (`fail` | `ignore`).

Tokens still on the pump.fun bonding curve have no LP, so liquidity / LP-lock rules are
marked n/a for them instead of failing.

## Auto scanner

Discovery (pump.fun stream, DexScreener profile poller, optional GMGN) -> de-duplicated
queue -> settle delay -> worker pool -> filters -> alerts. Tokens whose data is too thin
are re-scanned automatically. `GET /scanner/status` shows live counters.

## Tests

    pip install -r requirements-dev.txt && pytest
