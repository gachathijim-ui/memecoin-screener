"""Command-line interface for one-shot token scans."""
import argparse
import asyncio
import json

from app.models.token import Chain
from app.risk.engine import RiskEngine


async def run(address: str, chain: Chain):
    engine = RiskEngine()
    try:
        report = await engine.scan(address, chain)
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    finally:
        await engine.close()


def main():
    parser = argparse.ArgumentParser(description="Memecoin rug-pull screener CLI")
    parser.add_argument("address", help="Token mint/contract address")
    parser.add_argument(
        "--chain",
        choices=[c.value for c in Chain],
        default=Chain.SOLANA.value,
    )
    args = parser.parse_args()
    asyncio.run(run(args.address, Chain(args.chain)))


if __name__ == "__main__":
    main()
