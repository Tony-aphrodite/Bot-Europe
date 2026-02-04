"""
Portal modules for EU Registry Bot
"""

from .base import BasePortal
from .portugal import PortugalPortal
from .france import FrancePortal

__all__ = [
    "BasePortal",
    "PortugalPortal",
    "FrancePortal",
]
