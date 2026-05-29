from __future__ import annotations

import threading
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Callable, TypeVar

T = TypeVar("T")

# redirect_stdout/redirect_stderr mutate process-global streams, so concurrent
# use from scanner worker threads can leave another thread writing to a closed
# StringIO. Keep all silenced calls behind one shared process-local lock.
_OUTPUT_REDIRECT_LOCK = threading.RLock()


def call_silenced(fn: Callable[..., T], *args, **kwargs) -> T:
    with _OUTPUT_REDIRECT_LOCK:
        stdout_sink = StringIO()
        stderr_sink = StringIO()
        with redirect_stdout(stdout_sink), redirect_stderr(stderr_sink):
            return fn(*args, **kwargs)
