import os
import subprocess

from ruff.__main__ import find_ruff_bin


def ruff_fix(path: str):
    ruff = find_ruff_bin()
    proc = subprocess.run(
        [
            os.fsdecode(ruff),
            "check",
            "--extend-select",
            "I",
            "--fix-only",
            path,
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Ruff failed to fix the generated code",
            proc.stdout.decode(),
            proc.stderr.decode(),
        )


def ruff_format(path: str):
    ruff = find_ruff_bin()
    proc = subprocess.run(
        [os.fsdecode(ruff), "format", path],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Ruff failed to format the generated code",
            proc.stdout.decode(),
            proc.stderr.decode(),
        )
