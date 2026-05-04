"""Run with `python -m moses_core`."""

from __future__ import annotations

import logging

import uvicorn

from . import config as _config
from .app import app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    uvicorn.run(app, host=_config.settings.host, port=_config.settings.port)


if __name__ == "__main__":
    main()
