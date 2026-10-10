import asyncio
import html
from typing import Optional

import httpx

from app.config import settings
from app.models.report import ScanReport

EMOJI = {
    "LOW_RISK": "\U0001F7E2",
    "MODERATE_RISK": "\U0001F7E1",
    "HIGH_RISK": "\U0001F7E0",
    "CRITICAL": "\U0001F534",
}
COLOR = {
    "LOW_RISK": 0x2ECC71,
    "MODERATE_RISK": 0xF1C40F,
    "HIGH_RISK": 0xE67E22,
    "CRITICAL": 0xE74C3C,
}


def alert_kind(report: ScanReport, mode: Optional[str] = None) -> Optional[str]:
    """Return 'PASSED' / 'RISK' if this report should alert, else None."""
    mode = (mode or settings.alert_mode).lower()
    passed = bool(report.filter_result and report.filter_result.passed)
    risky = report.verdict in ("HIGH_RISK", "CRITICAL")
    if mode == "pass" and passed:
        return "PASSED"
    if mode == "risky" and risky:
        return "RISK"
    if mode == "both":
        if passed:
            return "PASSED"
        if risky:
            return "RISK"
    return None


def _usd(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"${v / div:.1f}{suffix}"
    return f"${v:,.0f}"


def _age(minutes: Optional[float]) -> str:
    if minutes is None:
        return "n/a"
    if minutes < 90:
        return f"{minutes:.0f}m"
    if minutes < 60 * 48:
        return f"{minutes / 60:.1f}h"
    return f"{minutes / 1440:.1f}d"


def _link(report: ScanReport) -> str:
    target = report.market.pair_address or report.token_address
    return f"https://dexscreener.com/{report.chain.value}/{target}"


def format_telegram(report: ScanReport, kind: str) -> str:
    fr = report.filter_result
    m = report.market
    e = html.escape
    title = "PASSED FILTERS" if kind == "PASSED" else "RISK WARNING"
    name = e(m.symbol or "?")
    lines = [
        f"{EMOJI.get(report.verdict, '?')} <b>{title}</b> ({e(fr.preset) if fr else 'n/a'})",
        f"<b>{name}</b> {e(m.name or '')} · {e(report.chain.value)} · {e(m.stage)}",
        f"<code>{e(report.token_address)}</code>",
        f"Verdict: {e(report.verdict)} · score {report.risk_score:.0f}/100 · confidence {report.confidence:.2f}",
        f"MC {_usd(m.market_cap)} · Liq {_usd(report.liquidity.total_usd if report.liquidity.applicable else None)}"
        f" · Vol1h {_usd(m.volume_1h)} · Age {_age(m.age_minutes)}",
    ]
    if report.holders.data_available:
        lines.append(
            f"Holders {report.holders.total_holders} · Top10 {report.holders.top_10_pct:.1f}%"
            f" · Dev {report.holders.dev_pct:.1f}%"
        )
    if report.wallets.data_available:
        lines.append(
            f"Snipers {report.wallets.sniper_pct:.1f}% · Bundlers {report.wallets.bundler_pct:.1f}%"
        )
    if fr:
        lines.append(f"Filters: {fr.passed_count} passed / {len(fr.failed)} failed")
        if fr.failed:
            lines.append("Failed: " + e(", ".join(fr.failed[:6])))
    if report.red_flags:
        lines.append("Flags: " + e(", ".join(report.red_flags[:6])))
    lines.append(f'<a href="{e(_link(report))}">DexScreener</a>')
    return "\n".join(lines)


async def send_telegram(report: ScanReport, kind: str = "PASSED") -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": format_telegram(report, kind),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        except httpx.HTTPError:
            pass


async def send_discord(report: ScanReport, kind: str = "PASSED") -> None:
    if not settings.discord_webhook_url:
        return
    m = report.market
    fr = report.filter_result
    title = "PASSED FILTERS" if kind == "PASSED" else "RISK WARNING"
    fields = [
        {"name": "Market cap", "value": _usd(m.market_cap), "inline": True},
        {
            "name": "Liquidity",
            "value": _usd(report.liquidity.total_usd) if report.liquidity.applicable else "bonding curve",
            "inline": True,
        },
        {"name": "Age", "value": _age(m.age_minutes), "inline": True},
        {"name": "Top 10", "value": f"{report.holders.top_10_pct:.1f}%" if report.holders.data_available else "n/a", "inline": True},
        {"name": "Snipers", "value": f"{report.wallets.sniper_pct:.1f}%" if report.wallets.data_available else "n/a", "inline": True},
        {"name": "Confidence", "value": f"{report.confidence:.2f}", "inline": True},
        {"name": "Red flags", "value": ", ".join(report.red_flags[:10]) or "None", "inline": False},
    ]
    if fr and fr.failed:
        fields.append({"name": "Failed filters", "value": ", ".join(fr.failed[:10]), "inline": False})
    payload = {
        "embeds": [
            {
                "title": f"{title}: {m.symbol or '?'} · {report.verdict} {report.risk_score:.0f}/100",
                "url": _link(report),
                "description": f"`{report.token_address}`\nChain: {report.chain.value}"
                               + (f" · preset: {fr.preset}" if fr else ""),
                "color": COLOR.get(report.verdict, 0x888888),
                "fields": fields,
            }
        ]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(settings.discord_webhook_url, json=payload)
        except httpx.HTTPError:
            pass


async def send_alerts(report: ScanReport, mode: Optional[str] = None) -> bool:
    """Send to every configured channel if the report qualifies. Returns True if sent."""
    kind = alert_kind(report, mode)
    if not kind:
        return False
    await asyncio.gather(send_telegram(report, kind), send_discord(report, kind))
    return True
