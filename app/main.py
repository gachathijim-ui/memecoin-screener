from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException

from app.alerts import send_discord, send_telegram
from app.models.report import ScanReport
from app.models.token import Chain
from app.risk.engine import RiskEngine
from app.auto_scanner import AutoScanner

engine = RiskEngine()
auto_scanner = AutoScanner(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    auto_scanner.start()
    yield
    for task in auto_scanner.tasks:
        task.cancel()
    await engine.close()


app = FastAPI(
    title="Memecoin Screener",
    version="1.0.0",
    description="Multi-platform memecoin rug-pull screener.",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/scan", response_model=ScanReport)
async def scan(
    address: str,
    background_tasks: BackgroundTasks,
    chain: Chain = Chain.SOLANA,
):
    try:
        report = await engine.scan(address, chain)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if report.verdict in ("HIGH_RISK", "CRITICAL"):
        background_tasks.add_task(send_telegram, report)
        background_tasks.add_task(send_discord, report)

    return report


@app.get("/scan/batch")
async def scan_batch(addresses: str, chain: Chain = Chain.SOLANA):
    addrs = [a.strip() for a in addresses.split(",") if a.strip()][:10]
    reports = []
    for addr in addrs:
        try:
            reports.append(await engine.scan(addr, chain))
        except Exception as e:
            reports.append({"address": addr, "error": str(e)})
    return reports
