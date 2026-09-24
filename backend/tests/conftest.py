import os
import pytest

BASE_URL = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
