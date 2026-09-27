from typing import Any, Dict

from .base import BaseConnector


class PadreConnector(BaseConnector):
    BASE_URL = "https://www.padre.gg"

    async def get_trench_metrics(self, mint: str) -> Dict[str, Any]:
        try:
            return await self._request(
                "GET", f"{self.BASE_URL}/api/trenches/token/{mint}"
            )
        except Exception:
            return {}
