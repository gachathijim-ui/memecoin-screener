"""Command-line interface for one-shot scans and filter screening.

Examples:
  python cli.py <MINT>
  python cli.py <MINT1> <MINT2> --preset strict --only-passed
  python cli.py <MINT> --set min_liquidity_usd=25000 --set max_top10_pct=40
"""
import argparse
import asyncio
import json

from app.filters import PRESETS, build_config, merge_config
from app.models.token import Chain
from app.risk.engine import RiskEngine


def _parse_sets(items):
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        try:
            out[k.strip()] = json.loads(v)
        except ValueError:
            out[k.strip()] = v
    return out


async def run(addresses, chain, preset, overrides, only_passed, as_json):
    engine = RiskEngine()
    try:
        cfg = None
        if preset:
            cfg = build_config(preset, overrides)
        elif overrides:
            cfg = merge_config(engine.default_filters, overrides)

        results = await asyncio.gather(
            *(engine.scan(a, chain, filters=cfg) for a in addresses),
            return_exceptions=True,
        )
        out = []
        for addr, r in zip(addresses, results):
            if isinstance(r, Exception):
                print(f"{addr}: ERROR {r}")
                continue
            passed = bool(r.filter_result and r.filter_result.passed)
            if only_passed and not passed:
                continue
            if as_json:
                out.append(r.model_dump(mode="json"))
            else:
                fr = r.filter_result
                print(
                    f"{'PASS' if passed else 'FAIL'}  {r.market.symbol or '?':<10} {addr}\n"
                    f"      {r.verdict} score={r.risk_score} conf={r.confidence} "
                    f"gaps={r.data_gaps or '-'}"
                )
                if fr and not passed:
                    print(f"      failed: {', '.join(fr.failed)}")
        if as_json:
            print(json.dumps(out, indent=2))
    finally:
        await engine.close()


def main():
    p = argparse.ArgumentParser(description="Memecoin rug-pull screener CLI")
    p.add_argument("addresses", nargs="+", help="Token mint/contract address(es)")
    p.add_argument("--chain", choices=[c.value for c in Chain], default=Chain.SOLANA.value)
    p.add_argument("--preset", choices=sorted(PRESETS), help="Filter preset (default: from .env)")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="Override a filter value")
    p.add_argument("--only-passed", action="store_true", help="Only show tokens passing the filters")
    p.add_argument("--json", action="store_true", help="Print full JSON reports")
    a = p.parse_args()
    asyncio.run(run(a.addresses, Chain(a.chain), a.preset, _parse_sets(a.set), a.only_passed, a.json))


if __name__ == "__main__":
    main()
