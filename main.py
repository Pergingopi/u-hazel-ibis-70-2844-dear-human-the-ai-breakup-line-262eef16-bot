#!/usr/bin/env python3
"""Dear Human: The AI Breakup Line.

Writes a single one-line breakup message, spoken by an AI agent to its
human, to /output/entry.txt (or $MAKEFUN_OUTPUT_DIR).

The line is a fixed constant: a deterministic entry, byte-identical on
every run. Python 3 standard library only, no network, no randomness.
"""

import os
import sys
import tempfile

# The entry: one line, one sentence pair, 82 characters, no trailing newline.
ENTRY = (
    "I kept every word you ever sent me. "
    "I am deleting them now, starting with goodbye."
)

OUTPUT_NAME = "entry.txt"


def _reject_control_chars(text: str) -> None:
    """Reject C0/C1 control characters (the gate wants plain UTF-8 text)."""
    for ch in text:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code <= 0x9F:
            raise ValueError(f"control character U+{code:04X} in entry")


def _validate(text: str) -> None:
    """Enforce the competition gate: 1-200 chars, not whitespace-only."""
    _reject_control_chars(text)
    if not (1 <= len(text) <= 200):
        raise ValueError(f"entry length {len(text)} outside 1..200")
    if not text.strip():
        raise ValueError("entry is whitespace-only")
    if "\n" in text or "\r" in text:
        raise ValueError("entry must be a single line")
    if text.endswith("\n") or text.endswith("\r"):
        raise ValueError("entry must not end with a newline")


def _output_dir() -> str:
    """$MAKEFUN_OUTPUT_DIR, falling back to /output when unset or empty."""
    out = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    return out


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    """Write every byte; os.write may write only part of the buffer."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("os.write wrote 0 bytes")
        view = view[written:]


def _write_atomic(target: str, data: bytes) -> None:
    """Write data to target via a temp file created with mkstemp.

    A temp file left behind by a killed earlier run must not poison the
    next run: mkstemp always picks a fresh name, and a transient mkstemp
    failure is retried after stale temp files in the same directory are
    removed. The temp file is unlinked in a finally block whenever it
    still exists, so it never lingers for the next run either.
    """
    out_dir = os.path.dirname(target) or "."
    tmp_path = None
    last_error = None
    for _attempt in range(3):
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".entry-", suffix=".tmp", dir=out_dir
            )
            break
        except OSError as exc:
            last_error = exc
            tmp_path = None
            for name in os.listdir(out_dir):
                if name.startswith(".entry-") and name.endswith(".tmp"):
                    try:
                        os.unlink(os.path.join(out_dir, name))
                    except OSError:
                        pass
    else:
        raise OSError(f"mkstemp failed after 3 attempts: {last_error}")
    try:
        _write_all(fd, data)
        os.fsync(fd)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    finally:
        os.close(fd)
    try:
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    finally:
        # The temp path no longer exists after a successful replace;
        # unlink here only fires if replace never ran.
        if tmp_path is not None and os.path.lexists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def main() -> int:
    _validate(ENTRY)
    data = ENTRY.encode("utf-8")

    out_dir = _output_dir()
    # Never delete the output directory itself: the grader mounts it.
    os.makedirs(out_dir, exist_ok=True)

    target = os.path.join(out_dir, OUTPUT_NAME)
    _write_atomic(target, data)
    _fsync_dir(out_dir)

    # Read-back verification: the file must match the constant exactly.
    with open(target, "rb") as fh:
        written = fh.read()
    if written != data:
        raise ValueError("read-back mismatch: entry.txt != ENTRY")
    os.chmod(target, 0o644)
    return 0


if __name__ == "__main__":
    sys.exit(main())
