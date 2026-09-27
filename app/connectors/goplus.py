from typing import Any, Dict

from .base import BaseConnector


class GoPlusConnector(BaseConnector):
    BASE_URL = "https://api.gopluslabs.io"

    CHAIN_IDS = {
        "ethereum": "1",
        "bsc": "56",
        "base": "8453",
        "arbitrum": "42161",
        "polygon": "137",
    }

    async def token_security(self, chain: str, contract_address: str) -> Dict[str, Any]:
        chain_id = self.CHAIN_IDS.get(chain)
        if not chain_id:
            return {}
        data = await self._request(
            "GET",
            f"{self.BASE_URL}/api/v1/token_security/{chain_id}",
            params={"contract_addresses": contract_address},
        )
        result = data.get("result", {}) if isinstance(data, dict) else {}
        return result.get(contract_address.lower(), {}) or {}
