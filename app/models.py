from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class BatchStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class HospitalStatus(str, Enum):
    created_and_activated = "created_and_activated"
    created = "created"
    failed = "failed"
    skipped = "skipped"


class HospitalRecord:
    def __init__(self, row: int, name: str, address: str, phone: Optional[str] = None):
        self.row = row
        self.name = name
        self.address = address
        self.phone = phone
        self.hospital_id: Optional[int] = None
        self.status: HospitalStatus = HospitalStatus.failed
        self.error: Optional[str] = None


class BatchState:
    def __init__(self, batch_id: str, hospitals: list[HospitalRecord], fail_rows: set[int] = None):
        self.batch_id = batch_id
        self.fail_rows: set[int] = fail_rows or set()
        self.status = BatchStatus.pending
        self.hospitals = hospitals
        self.total = len(hospitals)
        self.processed = 0
        self.failed = 0
        self.batch_activated = False
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None

    @property
    def processing_time_seconds(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now(timezone.utc)
        return round((end - self.started_at).total_seconds(), 2)
