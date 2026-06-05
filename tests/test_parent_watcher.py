import conda_meta_mcp.parent_watcher as parent_watcher


def test_parent_watcher_worker__interrupts_after_parent_exit(monkeypatch):
    calls = {}

    def wait_for_process_exit(pid):
        calls["pid"] = pid
        return True

    def interrupt_process():
        calls["interrupted"] = True

    monkeypatch.setattr(parent_watcher.os, "getppid", lambda: 123)

    parent_watcher._parent_watcher_worker(wait_for_process_exit, interrupt_process)

    assert calls == {"pid": 123, "interrupted": True}


def test_parent_watcher_worker__does_not_interrupt_if_parent_wait_unavailable(
    monkeypatch,
):
    calls = {}

    def wait_for_process_exit(pid):
        calls["pid"] = pid
        return False

    def interrupt_process():
        calls["interrupted"] = True

    monkeypatch.setattr(parent_watcher.os, "getppid", lambda: 123)

    parent_watcher._parent_watcher_worker(wait_for_process_exit, interrupt_process)

    assert calls == {"pid": 123}


def test_parent_watcher_worker__interrupts_if_parent_already_ended(monkeypatch):
    calls = {}

    def wait_for_process_exit(pid):
        calls["pid"] = pid
        return False

    def interrupt_process():
        calls["interrupted"] = True

    monkeypatch.setattr(parent_watcher.os, "getppid", lambda: 1)

    parent_watcher._parent_watcher_worker(wait_for_process_exit, interrupt_process)

    assert calls == {"interrupted": True}


def test_interrupt_process__raises_sigint(monkeypatch):
    calls = {}

    def raise_signal(sig):
        calls["signal"] = sig

    monkeypatch.setattr(parent_watcher.signal, "raise_signal", raise_signal)

    parent_watcher._interrupt_process()

    assert calls == {"signal": parent_watcher.signal.SIGINT}


def test_wait_for_parent_exit__returns_after_parent_changes(monkeypatch):
    parent_pids = iter([123, 1])

    monkeypatch.setattr(parent_watcher.os, "name", "posix")
    monkeypatch.setattr(parent_watcher.os, "getppid", lambda: next(parent_pids))
    monkeypatch.setattr(parent_watcher.time, "sleep", lambda seconds: None)

    assert parent_watcher._wait_for_parent_exit(123) is True


def test_start_parent_watcher__starts(monkeypatch):
    calls = {}

    class FakeThread:
        def __init__(self, *, target, args, name, daemon):
            calls["target"] = target
            calls["args"] = args
            calls["name"] = name
            calls["daemon"] = daemon

        def start(self):
            calls["started"] = True

    monkeypatch.setattr(parent_watcher.threading, "Thread", FakeThread)

    thread = parent_watcher.start_parent_watcher()

    assert isinstance(thread, FakeThread)
    assert calls == {
        "target": parent_watcher._parent_watcher_worker,
        "args": (),
        "name": "conda-meta-mcp-parent-watcher",
        "daemon": True,
        "started": True,
    }
