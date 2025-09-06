from .cli_help import register_cli_help
from .import_mapping import register_import_mapping
from .info import register_info
from .pkg_insights import register_package_insights
from .pkg_search import register_package_search

TOOLS = [
    register_cli_help,
    register_info,
    register_package_insights,
    register_package_search,
    register_import_mapping,
]

__all__ = ["TOOLS"]
