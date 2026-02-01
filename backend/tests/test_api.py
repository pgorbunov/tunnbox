import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.database import create_user, get_user_count
from app.dependencies import get_password_hash


@pytest.fixture
async def client():
    """Create async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(client):
    """Create authenticated client."""
    # Create test user
    hashed_password = get_password_hash("testpassword123")
    await create_user("testuser", hashed_password, is_admin=True)

    # Login
    response = await client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Set authorization header
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_check_setup_empty_db(client):
    """Test setup check with empty database."""
    response = await client.get("/api/auth/check-setup")
    assert response.status_code == 200
    assert response.json()["setup_required"] is True


@pytest.mark.asyncio
async def test_setup_admin(client):
    """Test admin setup."""
    response = await client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "adminpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_setup_admin_already_exists(client):
    """Test setup fails when admin already exists."""
    # Create first admin
    await client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "adminpassword123"}
    )

    # Try to create another
    response = await client.post(
        "/api/auth/setup",
        json={"username": "admin2", "password": "adminpassword123"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    """Test successful login."""
    # First setup admin
    await client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "adminpassword123"}
    )

    # Login
    response = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "adminpassword123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    # First setup admin
    await client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "adminpassword123"}
    )

    # Try wrong password
    response = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(auth_client):
    """Test getting current user info."""
    response = await auth_client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    """Test that unauthorized requests are rejected."""
    response = await client.get("/api/interfaces")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_interfaces(auth_client):
    """Test listing interfaces (may be empty)."""
    response = await auth_client.get("/api/interfaces")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
