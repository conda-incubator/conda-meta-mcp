from .cli_help import register_cli_help
from .import_mapping import register_import_mapping
from .info import register_info
from .pkg_insights import register_package_insights
from .pkg_search import register_package_search
from .pypi_to_conda import register_pypi_to_conda
from .repoquery import register_repoquery

TOOLS = [
    register_cli_help,
    register_info,
    register_package_insights,
    register_package_search,
    register_repoquery,
    register_import_mapping,
    register_pypi_to_conda,
]

__all__ = ["TOOLS"]
