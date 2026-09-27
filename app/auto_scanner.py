# app/auto_scanner.py
import asyncio
import json
import logging
import websockets
from typing import Optional

from app.risk.engine import RiskEngine
from app.alerts import send_telegram, send_discord
from app.models.token import Chain

logger = logging.getLogger("auto_scanner")


class AutoScanner:
    def __init__(self, engine: RiskEngine):
        self.engine = engine
        self.scanned_tokens = set()
        self.tasks = []

    async def handle_new_token(self, address: str, chain: Chain = Chain.SOLANA):
        """Triggers a scan for a new token address if not already scanned."""
        if address in self.scanned_tokens:
            return
        self.scanned_tokens.add(address)
        logger.info(f"Auto-scanning new token: {address}")

        try:
            report = await self.engine.scan(address, chain)
            logger.info(
                f"Scan complete for {address}: "
                f"{report.verdict} ({report.risk_score})"
            )

            if report.verdict in ("HIGH_RISK", "CRITICAL"):
                await send_telegram(report)
                await send_discord(report)
        except Exception as e:
            logger.error(f"Error scanning {address}: {e}")

    # --- Pump.fun Listener (via PumpPortal) ---
    async def listen_pumpfun(self):
        uri = "wss://pumpportal.fun/api/data"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    logger.info("Connected to Pump.fun (PumpPortal) stream")

                    async for message in ws:
                        data = json.loads(message)
                        if data.get("method") == "newToken" or "mint" in data:
                            mint = data.get("mint") or data.get("token")
                            if mint:
                                asyncio.create_task(
                                    self.handle_new_token(mint, Chain.SOLANA)
                                )
            except Exception as e:
                logger.warning(
                    f"Pump.fun stream disconnected: {e}. Reconnecting in 5s..."
                )
                await asyncio.sleep(5)

    # --- GMGN.ai Listener ---
    async def listen_gmgn(self):
        try:
            from gmgnapi import GmGnClient
        except ImportError:
            logger.error("gmgnapi not installed. Run: pip install gmgnapi")
            return

        async def on_new_pool(pool_info):
            if pool_info.pools:
                token_address = getattr(pool_info.pools[0].bti, "s", None)
                if token_address:
                    asyncio.create_task(
                        self.handle_new_token(token_address, Chain.SOLANA)
                    )

        try:
            client = GmGnClient()
            client.on_new_pool(on_new_pool)
            await client.connect()
            await client.subscribe_new_pools()
            logger.info("Connected to GMGN.ai new pools stream")
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"GMGN stream error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)

    # --- FOMO Listener (polling placeholder) ---
    async def listen_fomo(self):
        logger.info("FOMO listener started (polling mode - not yet implemented)")
        while True:
            await asyncio.sleep(30)

    def start(self):
        loop = asyncio.get_event_loop()
        self.tasks = [
            loop.create_task(self.listen_pumpfun()),
            loop.create_task(self.listen_gmgn()),
            loop.create_task(self.listen_fomo()),
        ]
        logger.info("All auto-scanner listeners started.")