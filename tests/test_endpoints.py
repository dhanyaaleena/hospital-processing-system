import io
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

VALID_CSV = b"name,address,phone\nGeneral Hospital,123 Main St,555-1234\nCity Clinic,456 Elm Ave,"
INVALID_CSV = b"name\nHospital X"
EXCEEDS_CSV = ("\n".join(f"Hospital {i},Address {i}" for i in range(1, 22))).encode()
EXCEEDS_CSV = b"name,address\n" + EXCEEDS_CSV

MOCK_CREATE_RESPONSE = {"id": 1, "name": "General Hospital", "active": False}
MOCK_ACTIVATE_RESPONSE = {"activated": 2}


def make_upload(content: bytes, filename: str = "hospitals.csv"):
    return ("file", (filename, io.BytesIO(content), "text/csv"))


@pytest.fixture
def mock_hospital_api():
    with patch("app.services.batch_service.hospital_api") as mock:
        mock.create_hospital = AsyncMock(
            side_effect=lambda name, address, batch_id, phone=None: {
                "id": hash(name) % 10000,
                "name": name,
                "active": False,
            }
        )
        mock.activate_batch = AsyncMock(return_value={"activated": True})
        yield mock


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_bulk_create_valid_csv(mock_hospital_api):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/hospitals/bulk",
            files=[make_upload(VALID_CSV)],
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["total_hospitals"] == 2
    assert "batch_id" in data


@pytest.mark.asyncio
async def test_bulk_create_invalid_csv():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/hospitals/bulk", files=[make_upload(INVALID_CSV)])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_create_exceeds_limit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/hospitals/bulk", files=[make_upload(EXCEEDS_CSV)])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_create_non_csv():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/hospitals/bulk", files=[make_upload(b"some data", filename="data.txt")])
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_status_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/hospitals/bulk/nonexistent-batch-id/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_batch_status_after_processing(mock_hospital_api):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/hospitals/bulk", files=[make_upload(VALID_CSV)])
        batch_id = create_resp.json()["batch_id"]
        # Give background task time to complete
        await asyncio.sleep(0.3)
        status_resp = await client.get(f"/hospitals/bulk/{batch_id}/status")

    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["batch_id"] == batch_id
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_validate_csv_valid():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/hospitals/bulk/validate",
            files=[make_upload(VALID_CSV)],
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["total_rows"] == 2


@pytest.mark.asyncio
async def test_validate_csv_invalid():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/hospitals/bulk/validate",
            files=[make_upload(INVALID_CSV)],
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.asyncio
async def test_bulk_create_with_api_failure():
    with patch("app.services.batch_service.hospital_api") as mock:
        mock.create_hospital = AsyncMock(side_effect=Exception("Connection error"))
        mock.activate_batch = AsyncMock(return_value={})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/hospitals/bulk", files=[make_upload(VALID_CSV)])
            assert resp.status_code == 202
            batch_id = resp.json()["batch_id"]
            await asyncio.sleep(0.3)
            status_resp = await client.get(f"/hospitals/bulk/{batch_id}/status")

    data = status_resp.json()
    assert data["failed_hospitals"] == 2
    assert data["processed_hospitals"] == 0
    assert data["batch_activated"] is False


@pytest.mark.asyncio
async def test_resume_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/hospitals/bulk/bad-batch-id/resume")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resume_completed_batch(mock_hospital_api):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/hospitals/bulk", files=[make_upload(VALID_CSV)])
        batch_id = create_resp.json()["batch_id"]
        await asyncio.sleep(0.3)
        resume_resp = await client.post(f"/hospitals/bulk/{batch_id}/resume")

    assert resume_resp.status_code == 409
