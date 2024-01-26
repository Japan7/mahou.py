import os
import re
import subprocess
from keyword import iskeyword

from ruff.__main__ import find_ruff_bin


def alias_invalid_id(name: str) -> tuple[str, str | None]:
    if name.isidentifier() and not iskeyword(name):
        return name, None
    else:
        fixed = re.sub("[^a-zA-Z0-9_]", "_", name)
        fixed = fixed.strip("_")
        fixed += "_alias"
        return fixed, name


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
