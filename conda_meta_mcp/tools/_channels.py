from fastmcp.exceptions import ToolError

SUPPORTED_CONDA_FORGE_CHANNEL = "conda-forge"


def require_conda_forge_channel(channel: str) -> str:
    normalized = str(channel).strip() if channel is not None else ""
    if normalized != SUPPORTED_CONDA_FORGE_CHANNEL:
        raise ToolError(
            f"No data available for channel {channel!r}. Try a different channel. "
            f"This tool currently supports only channel='{SUPPORTED_CONDA_FORGE_CHANNEL}'."
        )
    return normalized
