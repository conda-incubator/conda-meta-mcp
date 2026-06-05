from __future__ import annotations

import ctypes
import os
import signal
import threading
import time

PARENT_WATCHER_ENV = "CONDA_META_MCP_PARENT_WATCHDOG"


def env_enabled(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


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


def _interrupt_process() -> None:
    # FastMCP has no stop hook, so reuse the Ctrl+C shutdown path instead of
    # bypassing cleanup with os._exit().
    signal.raise_signal(signal.SIGINT)


def _parent_watcher_worker(
    wait_for_process_exit=_wait_for_parent_exit,
    interrupt_process=_interrupt_process,
) -> None:
    pid = os.getppid()
    if pid == 1 or wait_for_process_exit(pid):
        interrupt_process()


def start_parent_watcher() -> threading.Thread:
    """Stop orphaned servers when MCP hosts or proxy parents disappear."""
    thread = threading.Thread(
        target=_parent_watcher_worker,
        args=(),
        name="conda-meta-mcp-parent-watcher",
        daemon=True,
    )
    thread.start()
    return thread
