import logging
import re

from app.config import settings
from app.models.token import Chain

_SOLANA_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(settings.log_level.upper())
    return logger


def validate_address(chain: Chain, address: str) -> str:
    """Return a normalised address or raise ValueError."""
    a = (address or "").strip()
    if chain == Chain.SOLANA:
        if not _SOLANA_RE.match(a):
            raise ValueError(f"Invalid Solana mint address: {address!r}")
        return a
    if not _EVM_RE.match(a):
        raise ValueError(f"Invalid {chain.value} contract address: {address!r}")
    return a.lower()
