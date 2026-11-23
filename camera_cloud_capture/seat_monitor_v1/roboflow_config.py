"""Read optional SLA-root .env without ever printing its contents."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_local_settings() -> None:
    env_file = ROOT / '.env'
    if env_file.is_file():
        try:
            from dotenv import load_dotenv
        except ImportError as exc:
            raise RuntimeError('Install python-dotenv: python -m pip install python-dotenv') from exc
        # Environment variables explicitly set in a terminal take precedence.
        load_dotenv(dotenv_path=env_file, override=False)


def model_id(default: str = 'seat-analysis-8ssal/1') -> str:
    load_local_settings()
    return os.environ.get('ROBOFLOW_MODEL_ID') or default
