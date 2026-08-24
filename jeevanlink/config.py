"""Load settings from a .env file.

Reads key=value pairs from a .env file in the project root and puts
them into the environment. Written by hand so the project needs no
extra dependency.

Real environment variables always win. On a host like Render the
dashboard values are already set, and this loader leaves them alone.
"""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path = None) -> int:
    """Load a .env file. Returns how many variables were set."""
    env_path = Path(path) if path else ENV_FILE

    if not env_path.is_file():
        return 0

    loaded = 0

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("export "):
            line = line[len("export "):].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Strip one layer of matching quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if not key or key in os.environ:
            continue

        os.environ[key] = value
        loaded += 1

    return loaded
