import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app

@pytest.fixture
def client(tmp_path):
    settings.database_path = str(tmp_path / "failurelab-test.db")
    settings.aws_mode = False
    settings.simulation_time_scale = 0.0
    with TestClient(app) as test_client:
        yield test_client
