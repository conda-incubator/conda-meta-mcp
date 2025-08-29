from .info import register_info
from .pkg_insights import register_package_insights

TOOLS = [register_info, register_package_insights]

__all__ = ["TOOLS"]
