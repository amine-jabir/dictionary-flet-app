"""
Utilities package for dict_core.
"""

from dict_core.utils.http_client import ResilientHttpClient
from dict_core.utils.logger import get_logger

__all__ = ["ResilientHttpClient", "get_logger"]
