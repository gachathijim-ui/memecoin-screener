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
    "LOW_RISK": 0x00FF00,
    "MODERATE_RISK": 0xFFFF00,
    "HIGH_RISK": 0xFFA500,
    "CRITICAL": 0xFF0000,
}


async def send_telegram(report: ScanReport) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    text = (
        f"{EMOJI.get(report.verdict, '?')} {report.verdict} - "
        f"{report.risk_score}/100\n"
        f"{report.token_address}\n"
        f"Chain: {report.chain.value}\n"
        f"Red flags: {len(report.red_flags)}\n"
        f"{', '.join(report.red_flags[:5]) or 'None'}"
    )
    url = (
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
        except httpx.HTTPError:
            pass


async def send_discord(report: ScanReport) -> None:
    if not settings.discord_webhook_url:
        return
    payload = {
        "embeds": [
            {
                "title": f"{report.verdict} - {report.risk_score}/100",
                "description": (
                    f"Token: {report.token_address}\n"
                    f"Chain: {report.chain.value}"
                ),
                "color": COLOR.get(report.verdict, 0x888888),
                "fields": [
                    {
                        "name": "Red Flags",
                        "value": ", ".join(report.red_flags[:10]) or "None",
                        "inline": False,
                    },
                    {
                        "name": "Liquidity",
                        "value": f"${report.liquidity.total_usd:,.0f}",
                        "inline": True,
                    },
                    {
                        "name": "Top 10 Holders",
                        "value": f"{report.holders.top_10_pct:.1f}%",
                        "inline": True,
                    },
                    {
                        "name": "Sniper %",
                        "value": f"{report.wallets.sniper_pct:.1f}%",
                        "inline": True,
                    },
                ],
            }
        ]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(settings.discord_webhook_url, json=payload)
        except httpx.HTTPError:
            pass
