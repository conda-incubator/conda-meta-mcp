from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Final

try:
    from ._version import __version__  # ty: ignore[unresolved-import]
except ImportError:  # pragma: no cover
    __version__ = "0.0.0.dev0+placeholder"

APP_VERSION: Final = __version__
