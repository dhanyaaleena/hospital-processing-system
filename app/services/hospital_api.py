import httpx
from typing import Optional
from app.config import settings


class HospitalAPIClient:
    def __init__(self):
        self.base_url = settings.hospital_api_base_url
        self.timeout = settings.request_timeout

    async def create_hospital(
        self,
        name: str,
        address: str,
        batch_id: str,
        phone: Optional[str] = None,
    ) -> dict:
        payload = {"name": name, "address": address, "creation_batch_id": batch_id}
        if phone:
            payload["phone"] = phone

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/hospitals/", json=payload)
            response.raise_for_status()
            return response.json()

    async def activate_batch(self, batch_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(
                f"{self.base_url}/hospitals/batch/{batch_id}/activate"
            )
            response.raise_for_status()
            return response.json()

    async def get_batch_hospitals(self, batch_id: str) -> list:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/hospitals/batch/{batch_id}")
            response.raise_for_status()
            return response.json()

    async def delete_batch(self, batch_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/hospitals/batch/{batch_id}"
            )
            response.raise_for_status()
            return response.json()


hospital_api = HospitalAPIClient()
