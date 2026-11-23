import pytest
from fastapi.testclient import TestClient

from foodhunt import web


@pytest.fixture(scope="session")
def client():
    # `with` runs the lifespan → starts the MCP session manager (once per process, like on Vercel)
    with TestClient(web.app) as c:
        yield c
