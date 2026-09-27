from typing import Any, Dict, List

from app.config import settings

from .base import BaseConnector


class HeliusConnector(BaseConnector):
    BASE_URL = "https://mainnet.helius-rpc.com"

    def _url(self) -> str:
        return f"{self.BASE_URL}/?api-key={settings.helius_api_key}"

    async def get_token_largest_accounts(self, mint: str) -> List[dict]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenLargestAccounts",
            "params": [mint],
        }
        data = await self._request("POST", self._url(), json=payload)
        return data.get("result", {}).get("value", [])

    async def get_token_supply(self, mint: str) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenSupply",
            "params": [mint],
        }
        data = await self._request("POST", self._url(), json=payload)
        return data.get("result", {}).get("value", {})

    async def get_signatures_for_address(
        self, address: str, limit: int = 100
    ) -> List[dict]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [address, {"limit": limit}],
        }
        data = await self._request("POST", self._url(), json=payload)
        return data.get("result", [])
