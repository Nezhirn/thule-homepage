"""Shared fixtures for the Homepage backend tests."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config  # noqa: E402
from main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data_paths(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    uploads = data_dir / "uploads"
    monkeypatch.setattr(config, "DATABASE_PATH", str(data_dir / "homepage.db"))
    monkeypatch.setattr(config, "UPLOADS_DIR", str(uploads))
    monkeypatch.setattr(config, "AUTH_TOKEN", None)
    monkeypatch.setattr(config, "FRONTEND_DIR", str(REPO_ROOT / "frontend"))
    return {"data": data_dir, "db": data_dir / "homepage.db", "uploads": uploads}


@pytest.fixture
def client(data_paths):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(data_paths, monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN", "test-secret-token")
    with TestClient(app) as test_client:
        yield test_client
