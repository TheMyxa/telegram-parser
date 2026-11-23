from contextlib import ExitStack, contextmanager
import errno
import os
from pathlib import Path

from errors import ProcessAlreadyRunningError


@contextmanager
def exclusive_file_lock(path, resource):
    """Nonblocking OS lock. Keep the sidecar inode; the OS releases on exit/crash."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            raise ProcessAlreadyRunningError(
                f"{resource} is already used by another Export/Watch process. Stop it before retrying."
            ) from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def telegram_writer_locks(session, archive_paths):
    session = str(session)
    if not session.endswith(".session"):
        session += ".session"
    resources = {str(Path(session).resolve()) + ".tg-lock": "Telegram session"}
    for path in archive_paths:
        resources[str(Path(path).resolve()) + ".tg-lock"] = "Channel archive"
    with ExitStack() as stack:
        for path, label in sorted(resources.items()):
            stack.enter_context(exclusive_file_lock(path, label))
        yield
