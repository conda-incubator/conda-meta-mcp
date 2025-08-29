from .info import register_info
from .pkg_insights import register_package_insights
from .pkg_search import register_package_search

TOOLS = [register_info, register_package_insights, register_package_search]

__all__ = ["TOOLS"]
