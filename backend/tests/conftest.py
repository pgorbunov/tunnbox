import pytest
import asyncio
import tempfile
import os
from pathlib import Path

# Set up test environment before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["WG_CONFIG_PATH"] = tempfile.mkdtemp()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """Set up a fresh database for each test."""
    from app.database import init_db, DB_PATH

    # Remove existing test database
    if os.path.exists(DB_PATH):
        os.unlink(DB_PATH)

    # Initialize fresh database
    await init_db()

    yield

    # Cleanup
    if os.path.exists(DB_PATH):
        os.unlink(DB_PATH)
