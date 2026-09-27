from typing import Any, Dict, List

from app.config import settings

from .base import BaseConnector


class GMGNConnector(BaseConnector):
    BASE_URL = "https://gmgn.ai"

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if settings.gmgn_api_key:
            h["Authorization"] = f"Bearer {settings.gmgn_api_key}"
        return h

    async def rugcheck(self, chain: str, token_address: str) -> Dict[str, Any]:
        try:
            return await self._request(
                "GET",
                f"{self.BASE_URL}/defi/quotation/v1/rugcheck/{chain}/{token_address}",
                headers=self._headers(),
            )
        except Exception:
            return {}

    async def token_holders(self, chain: str, token_address: str) -> Dict[str, Any]:
        try:
            return await self._request(
                "GET",
                f"{self.BASE_URL}/defi/quotation/v1/token_holders/{chain}/{token_address}",
                headers=self._headers(),
            )
        except Exception:
            return {}

    async def trending(self, chain: str, timeframe: str = "1h") -> List[dict]:
        try:
            data = await self._request(
                "GET",
                f"{self.BASE_URL}/defi/quotation/v1/rank/{chain}/swaps/{timeframe}",
                headers=self._headers(),
            )
            return data.get("data", {}).get("rank", [])
        except Exception:
            return []
