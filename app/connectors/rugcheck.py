from typing import Any, Dict

from .base import BaseConnector


class RugCheckConnector(BaseConnector):
    BASE_URL = "https://api.rugcheck.xyz/v1"

    async def scan_token(self, mint: str) -> Dict[str, Any]:
        return await self._request("GET", f"{self.BASE_URL}/tokens/{mint}/report")

    async def token_summary(self, mint: str) -> Dict[str, Any]:
        return await self._request(
            "GET", f"{self.BASE_URL}/tokens/{mint}/report/summary"
        )
