import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from app.alerts import send_alerts
from app.auto_scanner import AutoScanner
from app.config import settings
from app.filters import PRESETS, build_config, merge_config
from app.models.filters import FilterConfig
from app.models.report import ScanReport
from app.models.token import Chain
from app.risk.engine import RiskEngine

engine = RiskEngine()
auto_scanner = AutoScanner(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_scan_enabled:
        auto_scanner.start()
    yield
    await auto_scanner.stop()
    await engine.close()


app = FastAPI(
    title="Memecoin Screener",
    version="2.0.0",
    description="Multi-chain memecoin rug-pull screener with configurable filters.",
    lifespan=lifespan,
)


def _resolve_filters(
    preset: Optional[str], overrides: Optional[Dict[str, Any]] = None
) -> Optional[FilterConfig]:
    """None -> use the engine's default (env-configured) filters."""
    try:
        if preset:
            return build_config(preset, overrides)
        if overrides:
            return merge_config(engine.default_filters, overrides)
        return None
    except ValueError as e:  # includes pydantic ValidationError
        raise HTTPException(status_code=400, detail=str(e))


async def _scan(address: str, chain: Chain, cfg: Optional[FilterConfig]) -> ScanReport:
    try:
        return await engine.scan(address, chain, filters=cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/filters/presets")
async def filter_presets():
    return {
        "default": engine.default_filters.preset,
        "presets": PRESETS,
        "active_config": engine.default_filters.model_dump(mode="json"),
    }


@app.get("/scanner/status")
async def scanner_status():
    return auto_scanner.status()


@app.get("/scan", response_model=ScanReport)
async def scan(
    address: str,
    background_tasks: BackgroundTasks,
    chain: Chain = Chain.SOLANA,
    preset: Optional[str] = None,
    alert: bool = True,
):
    report = await _scan(address, chain, _resolve_filters(preset))
    if alert:
        background_tasks.add_task(send_alerts, report)
    return report


class ScanRequest(BaseModel):
    address: str
    chain: Chain = Chain.SOLANA
    preset: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None  # overrides on top of preset/default


@app.post("/scan", response_model=ScanReport)
async def scan_custom(req: ScanRequest, background_tasks: BackgroundTasks, alert: bool = False):
    report = await _scan(req.address, req.chain, _resolve_filters(req.preset, req.filters))
    if alert:
        background_tasks.add_task(send_alerts, report)
    return report


class ScreenRequest(BaseModel):
    addresses: List[str]
    chain: Chain = Chain.SOLANA
    preset: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@app.post("/screen")
async def screen(req: ScreenRequest):
    """Scan many tokens concurrently and return only the ones passing the filters."""
    addrs = list(dict.fromkeys(a.strip() for a in req.addresses if a.strip()))[:50]
    cfg = _resolve_filters(req.preset, req.filters)
    sem = asyncio.Semaphore(settings.scan_workers)

    async def one(addr: str):
        async with sem:
            try:
                return await engine.scan(addr, req.chain, filters=cfg)
            except Exception as e:  # noqa: BLE001
                return {"address": addr, "error": str(e)}

    results = await asyncio.gather(*(one(a) for a in addrs))

    passed, failed, errors = [], [], []
    for r in results:
        if isinstance(r, dict):
            errors.append(r)
        elif r.filter_result and r.filter_result.passed:
            passed.append(r)
        else:
            failed.append({
                "address": r.token_address,
                "verdict": r.verdict,
                "risk_score": r.risk_score,
                "confidence": r.confidence,
                "failed_rules": r.filter_result.failed if r.filter_result else [],
            })
    return {"scanned": len(addrs), "passed": passed, "failed": failed, "errors": errors}


@app.get("/scan/batch")
async def scan_batch(addresses: str, chain: Chain = Chain.SOLANA, preset: Optional[str] = None):
    addrs = [a.strip() for a in addresses.split(",") if a.strip()][:10]
    cfg = _resolve_filters(preset)
    sem = asyncio.Semaphore(settings.scan_workers)

    async def one(addr: str):
        async with sem:
            try:
                return await engine.scan(addr, chain, filters=cfg)
            except Exception as e:  # noqa: BLE001
                return {"address": addr, "error": str(e)}

    return await asyncio.gather(*(one(a) for a in addrs))
