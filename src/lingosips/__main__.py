"""Entry point for the lingosips application.

Startup sequence (strict order):
1. Configure structured logging
2. Ensure ~/.lingosips data directory exists
3. Run Alembic migrations (blocking — server waits until schema is ready)
4. Start uvicorn bound to 127.0.0.1:7842 (NEVER 0.0.0.0)
   - Browser open is triggered as a startup hook inside app.py
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Application entry point — run via `lingosips` CLI or `python -m lingosips`."""
    # 1. Configure structured logging first (before any other imports that log)
    from lingosips.core.logging import configure_logging

    configure_logging()

    # 2. Ensure data directory and subdirectories exist
    data_dir = Path.home() / ".lingosips"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "models").mkdir(exist_ok=True)

    # 3. Run Alembic migrations — blocking; uvicorn must NOT start until complete
    try:
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            check=True,
        )
    except subprocess.CalledProcessError:
        sys.stderr.write("Migration failed — aborting startup\n")
        sys.exit(1)

    # 4. Start uvicorn — MUST bind to 127.0.0.1 only, never 0.0.0.0
    import uvicorn

    uvicorn.run(
        "lingosips.api.app:app",
        host="127.0.0.1",
        port=7842,
        reload=False,
    )


if __name__ == "__main__":
    main()
