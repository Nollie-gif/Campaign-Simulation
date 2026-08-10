from __future__ import annotations

import errno
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import os

if os.name == "nt":
    import msvcrt  # type: ignore
else:
    import fcntl  # type: ignore


class LockAcquireTimeout(RuntimeError):
    pass


@contextmanager
def advisory_lock(lock_path: Path, timeout_seconds: float = 2.0, poll_interval: float = 0.01) -> Iterator[None]:
    """
    Cross-platform advisory file lock context manager.

    - The lock file is persistent; its existence does not imply ownership.
    - Ownership is represented only by an OS advisory lock held on an open file object.
    - The file object is kept open for the duration of the context; it is the single owner
      of the underlying file descriptor and thus the single entity that closes it.
    - On exit the lock is released and the file object is closed automatically by the
      with-open context.
    - The function retries only on genuine lock-contention errors (platform-specific),
      and propagates other OSError conditions immediately.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Open the persistent lock file in binary read-write mode (create if missing).
    # The with-open ensures the file descriptor is closed exactly once by the file object.
    with open(lock_path, "a+b") as lock_file:
        fd = lock_file.fileno()
        deadline = time.monotonic() + float(timeout_seconds)
        last_exc = None

        # Acquisition loop
        while True:
            try:
                if os.name == "nt":
                    # Windows: ensure deterministic position before locking
                    lock_file.seek(0)
                    try:
                        # Lock one byte at offset 0 in non-blocking mode
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    except OSError as e:
                        # Retry only on documented blocking error (EACCES)
                        if getattr(e, "errno", None) == errno.EACCES:
                            last_exc = e
                        else:
                            # Unexpected error: propagate immediately
                            raise
                    else:
                        # Lock acquired
                        break
                else:
                    # POSIX: attempt non-blocking exclusive flock
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError as e:
                        # Retry only on EACCES or EAGAIN; propagate others.
                        if e.errno in (errno.EACCES, errno.EAGAIN):
                            last_exc = e
                        else:
                            raise
                    else:
                        # Lock acquired
                        break

                # Lock not acquired due to contention; check timeout
                if time.monotonic() >= deadline:
                    if last_exc is not None:
                        raise LockAcquireTimeout(f"advisory lock acquisition timed out: {lock_path}") from last_exc
                    raise LockAcquireTimeout(f"advisory lock acquisition timed out: {lock_path}")

                time.sleep(poll_interval)

            except Exception:
                # Any unexpected exception during acquisition should propagate;
                # the with-open will ensure the file object closes the fd exactly once.
                raise

        # At this point the advisory lock is held and lock_file remains open.
        try:
            yield
        finally:
            # Attempt to release the advisory lock. Let unlock errors surface.
            if os.name == "nt":
                # Seek before unlocking as required.
                lock_file.seek(0)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
