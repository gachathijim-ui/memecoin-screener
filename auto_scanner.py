"""Discovery -> queue -> scan -> filter -> alert pipeline."""
import asyncio
import json
import time
from collections import Counter, OrderedDict
from typing import Dict, List, Optional, Tuple

from app.alerts import send_alerts
from app.config import settings
from app.models.token import Chain
from app.risk.engine import RiskEngine
from app.utils import get_logger

logger = get_logger("auto_scanner")

_CHAIN_BY_VALUE: Dict[str, Chain] = {c.value: c for c in Chain}
Job = Tuple[str, Chain, int]  # address, chain, attempt


class AutoScanner:
    def __init__(self, engine: RiskEngine):
        self.engine = engine
        self.queue: "asyncio.Queue[Job]" = asyncio.Queue(maxsize=settings.queue_size)
        self.tasks: List[asyncio.Task] = []
        self._timers: set = set()
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        self.stats: Counter = Counter()

    # ------------------------------------------------------------------ #
    # De-duplication (bounded + expiring, so memory never grows forever)
    # ------------------------------------------------------------------ #
    def _mark_seen(self, key: str) -> bool:
        """Return True if newly marked, False if it was already seen recently."""
        now = time.monotonic()
        ttl = settings.dedupe_ttl_seconds
        while self._seen:
            oldest_key, ts = next(iter(self._seen.items()))
            if now - ts > ttl or len(self._seen) > settings.dedupe_max_entries:
                self._seen.popitem(last=False)
            else:
                break
        if key in self._seen:
            return False
        self._seen[key] = now
        return True

    # ------------------------------------------------------------------ #
    # Intake
    # ------------------------------------------------------------------ #
    def submit(self, address: str, chain: Chain = Chain.SOLANA, source: str = "manual") -> bool:
        """Queue a newly discovered token (after a short settle delay)."""
        key = f"{chain.value}:{address.lower() if chain != Chain.SOLANA else address}"
        if not self._mark_seen(key):
            self.stats["duplicates"] += 1
            return False
        self.stats["discovered"] += 1
        self.stats[f"source_{source}"] += 1
        self._schedule((address, chain, 0), settings.scan_delay_seconds)
        return True

    def _schedule(self, job: Job, delay: float) -> None:
        async def later():
            await asyncio.sleep(delay)
            try:
                self.queue.put_nowait(job)
            except asyncio.QueueFull:
                self.stats["dropped_queue_full"] += 1
                logger.warning("Queue full, dropping %s", job[0])

        t = asyncio.create_task(later())
        self._timers.add(t)
        t.add_done_callback(self._timers.discard)

    # ------------------------------------------------------------------ #
    # Workers
    # ------------------------------------------------------------------ #
    async def _worker(self, n: int) -> None:
        while True:
            job = await self.queue.get()
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                self.stats["errors"] += 1
                logger.error("Worker %d failed on %s: %s", n, job[0], e)
            finally:
                self.queue.task_done()

    async def _process(self, job: Job) -> None:
        address, chain, attempt = job
        report = await self.engine.scan(address, chain, fresh=attempt > 0)
        self.stats["scanned"] += 1

        # Brand-new tokens often aren't indexed yet: look again before judging.
        if (
            report.confidence < settings.rescan_min_confidence
            and attempt + 1 < settings.rescan_attempts
        ):
            self.stats["rescheduled"] += 1
            logger.info("Low confidence (%.2f) for %s, rescanning", report.confidence, address)
            self._schedule((address, chain, attempt + 1), settings.scan_delay_seconds * 2)
            return

        fr = report.filter_result
        passed = bool(fr and fr.passed)
        self.stats["passed_filters" if passed else "failed_filters"] += 1
        logger.info(
            "%s %s: %s score=%.1f conf=%.2f filters=%s",
            chain.value, address, report.verdict, report.risk_score, report.confidence,
            "PASS" if passed else f"FAIL({','.join((fr.failed if fr else [])[:4])})",
        )
        if await send_alerts(report):
            self.stats["alerts_sent"] += 1

    # ------------------------------------------------------------------ #
    # Discovery sources
    # ------------------------------------------------------------------ #
    async def listen_pumpfun(self) -> None:
        try:
            import websockets
        except ImportError:
            logger.error("websockets not installed; pump.fun listener disabled")
            return
        uri = "wss://pumpportal.fun/api/data"
        while True:
            try:
                async with websockets.connect(uri, ping_interval=20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    logger.info("Connected to Pump.fun (PumpPortal) stream")
                    async for message in ws:
                        try:
                            data = json.loads(message)
                        except ValueError:
                            continue
                        mint = data.get("mint") or data.get("token")
                        if mint and data.get("txType", "create") == "create":
                            self.submit(mint, Chain.SOLANA, "pumpfun")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning("Pump.fun stream dropped: %s. Reconnecting in 5s", e)
                await asyncio.sleep(5)

    async def listen_gmgn(self) -> None:
        try:
            from gmgnapi import GmGnClient
        except ImportError:
            logger.error("gmgnapi not installed (pip install gmgnapi); GMGN listener disabled")
            return

        async def on_new_pool(pool_info):
            if pool_info.pools:
                token = getattr(pool_info.pools[0].bti, "s", None)
                if token:
                    self.submit(token, Chain.SOLANA, "gmgn")

        while True:
            try:
                client = GmGnClient()
                client.on_new_pool(on_new_pool)
                await client.connect()
                await client.subscribe_new_pools()
                logger.info("Connected to GMGN new-pools stream")
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning("GMGN stream error: %s. Reconnecting in 10s", e)
                await asyncio.sleep(10)

    async def listen_dexscreener_profiles(self) -> None:
        """Polls DexScreener's latest token profiles (all supported chains)."""
        logger.info("DexScreener profile poller started")
        while True:
            try:
                for p in await self.engine.dexscreener.latest_token_profiles():
                    chain = _CHAIN_BY_VALUE.get(p.get("chainId"))
                    addr = p.get("tokenAddress")
                    if chain and addr:
                        self.submit(addr, chain, "dexscreener")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning("DexScreener poll failed: %s", e)
            await asyncio.sleep(settings.dexscreener_poll_seconds)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self.tasks = [
            asyncio.create_task(self._worker(i)) for i in range(settings.scan_workers)
        ]
        if settings.enable_pumpfun:
            self.tasks.append(asyncio.create_task(self.listen_pumpfun()))
        if settings.enable_gmgn:
            self.tasks.append(asyncio.create_task(self.listen_gmgn()))
        if settings.enable_dexscreener_profiles:
            self.tasks.append(asyncio.create_task(self.listen_dexscreener_profiles()))
        logger.info(
            "Auto-scanner started: %d workers, preset=%s, alert_mode=%s",
            settings.scan_workers, self.engine.default_filters.preset, settings.alert_mode,
        )

    async def stop(self) -> None:
        for t in [*self.tasks, *self._timers]:
            t.cancel()
        await asyncio.gather(*self.tasks, *self._timers, return_exceptions=True)
        self.tasks = []

    def status(self) -> dict:
        return {
            "running": any(not t.done() for t in self.tasks),
            "queue_size": self.queue.qsize(),
            "pending_timers": len(self._timers),
            "tracked_tokens": len(self._seen),
            "preset": self.engine.default_filters.preset,
            "alert_mode": settings.alert_mode,
            "stats": dict(self.stats),
        }
