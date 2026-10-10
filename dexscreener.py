from typing import List

from .base import BaseConnector


class DexScreenerConnector(BaseConnector):
    BASE_URL = "https://api.dexscreener.com"

    async def get_token_pairs(self, chain: str, token_address: str) -> List[dict]:
        data = await self._request(
            "GET",
            f"{self.BASE_URL}/token-pairs/v1/{chain}/{token_address}",
        )
        return data if isinstance(data, list) else []

    async def get_tokens(self, chain: str, token_addresses: List[str]) -> List[dict]:
        joined = ",".join(token_addresses[:30])
        data = await self._request(
            "GET",
            f"{self.BASE_URL}/tokens/v1/{chain}/{joined}",
        )
        return data if isinstance(data, list) else []

    async def search(self, query: str) -> List[dict]:
        data = await self._request(
            "GET",
            f"{self.BASE_URL}/latest/dex/search",
            params={"q": query},
        )
        return data.get("pairs", []) if isinstance(data, dict) else []

    async def latest_token_profiles(self) -> List[dict]:
        """Recently created token profiles across all chains (discovery feed)."""
        data = await self._request("GET", f"{self.BASE_URL}/token-profiles/latest/v1")
        return data if isinstance(data, list) else []
