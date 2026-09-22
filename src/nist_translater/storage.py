"""JSON persistence with validation before an atomic replacement."""

import json
import os
import tempfile
from pathlib import Path


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    json.loads(serialized)  # Refuse invalid output before replacing the existing file.
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", suffix=".tmp",
                                         delete=False) as handle:
            name = handle.name
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        json.loads(Path(name).read_text(encoding="utf-8"))
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
