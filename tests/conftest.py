"""Pytest fixtures — PYTHONPATH = pidrive/."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIDRIVE_DIR = Path(__file__).resolve().parents[1] / "pidrive"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _pidrive_on_path():
    p = str(PIDRIVE_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def pidrive_dir() -> Path:
    return PIDRIVE_DIR
