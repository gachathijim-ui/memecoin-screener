from typing import Any, Dict, List

from .base import BaseConnector


class PumpFunConnector(BaseConnector):
    BASE_URL = "https://frontend-api-v3.pump.fun"

    async def get_coin(self, mint: str) -> Dict[str, Any]:
        try:
            return await self._request("GET", f"{self.BASE_URL}/coins/{mint}")
        except Exception:
            return {}

    async def get_live_coins(self, limit: int = 60) -> List[dict]:
        try:
            data = await self._request(
                "GET",
                f"{self.BASE_URL}/coins/currently-live",
                params={
                    "offset": 0,
                    "limit": limit,
                    "sort": "currently_live",
                    "order": "DESC",
                },
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []
