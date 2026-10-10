import json
from typing import Any, Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- API keys / alert targets ---
    helius_api_key: str = ""
    gmgn_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # --- server ---
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # --- filters ---
    # strict | balanced | degen | off
    filter_preset: str = "balanced"
    # JSON object of overrides applied on top of the preset,
    # e.g. {"min_liquidity_usd": 25000, "max_top10_pct": 40}
    filter_overrides_json: str = ""

    # --- alerts ---
    # pass  -> alert when a token PASSES the filters (opportunity feed)
    # risky -> alert when verdict is HIGH_RISK / CRITICAL (warning feed)
    # both  -> either of the above
    # none  -> never alert
    alert_mode: str = "pass"

    # --- auto scanner ---
    auto_scan_enabled: bool = True
    enable_pumpfun: bool = True
    enable_gmgn: bool = False
    enable_dexscreener_profiles: bool = True
    dexscreener_poll_seconds: int = 60
    scan_delay_seconds: int = 45          # let indexers catch up before scanning
    scan_workers: int = 4
    queue_size: int = 500
    dedupe_ttl_seconds: int = 3600
    dedupe_max_entries: int = 5000
    rescan_attempts: int = 2              # total attempts if data is too thin
    rescan_min_confidence: float = 0.5

    # --- engine ---
    scan_cache_ttl_seconds: int = 60
    module_timeout_seconds: float = 20.0

    def filter_overrides(self) -> Dict[str, Any]:
        if not self.filter_overrides_json.strip():
            return {}
        data = json.loads(self.filter_overrides_json)
        if not isinstance(data, dict):
            raise ValueError("FILTER_OVERRIDES_JSON must be a JSON object")
        return data


settings = Settings()
