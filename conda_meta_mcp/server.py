from __future__ import annotations

import asyncio
import contextlib
import ctypes
import importlib
import os
import sys
import threading
import time
from typing import TYPE_CHECKING

from fastmcp import FastMCP

if TYPE_CHECKING:
    import argparse

SERVICE_NAME = "Conda ECO System Meta Data MCP"
_PARENT_WATCHDOG_ENV = "CONDA_META_MCP_PARENT_WATCHDOG"
_PARENT_PID_ENV = "CONDA_META_MCP_PARENT_PID"

_periodic_cleanup_task: asyncio.Task | None = None


def _env_enabled(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _parent_pid() -> int:
    configured_pid = os.getenv(_PARENT_PID_ENV)
    if configured_pid:
        with contextlib.suppress(ValueError):
            return int(configured_pid)
    return os.getppid()


def _wait_for_process_exit_windows(pid: int) -> bool:
    """Wait for the recorded Windows parent process to exit."""
    win_dll = getattr(ctypes, "WinDLL", None)
    if win_dll is None:  # pragma: no cover - defensive for non-Windows tests
        return False

    kernel32 = win_dll("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        return True

    try:
        wait_result = kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)  # INFINITE
    finally:
        kernel32.CloseHandle(handle)

    return wait_result == 0  # WAIT_OBJECT_0


def _wait_for_parent_exit(pid: int) -> bool:
    if os.name == "nt":
        return _wait_for_process_exit_windows(pid)

    while os.getppid() == pid:
        time.sleep(1)
    return True


def _exit_process(code: int) -> None:
    os._exit(code)


def _parent_watchdog_worker(
    pid: int,
    wait_for_process_exit=_wait_for_parent_exit,
    exit_process=_exit_process,
) -> None:
    if wait_for_process_exit(pid):
        exit_process(0)


def _start_parent_watchdog() -> threading.Thread | None:
    """Stop orphaned servers when MCP hosts or proxy parents disappear."""
    if not _env_enabled(_PARENT_WATCHDOG_ENV, default=True):
        return None

    thread = threading.Thread(
        target=_parent_watchdog_worker,
        args=(_parent_pid(),),
        name="conda-meta-mcp-parent-watchdog",
        daemon=True,
    )
    thread.start()
    return thread


def _build_code_mode_transform():
    code_mode = importlib.import_module("fastmcp.experimental.transforms.code_mode")

    sandbox = code_mode.MontySandboxProvider(
        limits={"max_duration_secs": 30, "max_memory": 2_000_000_000}
    )
    return code_mode.CodeMode(
        discovery_tools=[code_mode.ListTools(), code_mode.GetSchemas()],
        sandbox_provider=sandbox,
    )


def setup_run(subparser: argparse._SubParsersAction):
    run_parser = subparser.add_parser("run", help="Run server")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    run_parser.add_argument("-c", "--code", action="store_true", help="Code Mode")
    run_parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Server transport (default: stdio)",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for non-stdio transports (e.g. streamable-http)",
    )
    run_parser.set_defaults(func=run_cmd)


def run_cmd(args):
    log_level = "DEBUG" if args.verbose else "INFO"
    os.environ["FASTMCP_LOG_LEVEL"] = log_level
    _start_parent_watchdog()
    mcp = setup_server(args.code)

    run_kwargs = {"transport": args.transport, "show_banner": False}
    if args.port is not None:
        run_kwargs["port"] = args.port

    mcp.run(**run_kwargs)


def setup_server(code=False) -> FastMCP:
    from conda_meta_mcp.tools import discover_tools
    from conda_meta_mcp.tools.cache_utils import clear_external_library_caches

    global _periodic_cleanup_task

    transforms = [_build_code_mode_transform()] if code else None

    instance = FastMCP(name=SERVICE_NAME, transforms=transforms)

    for tool_fn in discover_tools():
        default_name = getattr(tool_fn, "__name__", "unknown")
        tool_name = getattr(tool_fn, "__mcp_tool_name__", default_name)
        instance.tool(tool_fn, name=tool_name)

    async def periodic_cleanup():
        """Periodically clear external library caches to prevent memory growth."""
        while True:
            await asyncio.sleep(1800)  # 30 minutes
            clear_external_library_caches()

    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop()
        _periodic_cleanup_task = asyncio.create_task(periodic_cleanup())

    return instance


# Enable usage of fastmcp cli
if "fastmcp" in sys.argv[0]:  # pragma: no cover
    mcp = setup_server()
