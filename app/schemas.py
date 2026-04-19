from pydantic import BaseModel
from typing import Optional, List
from app.models import BatchStatus, HospitalStatus


class HospitalResult(BaseModel):
    row: int
    hospital_id: Optional[int] = None
    name: str
    status: HospitalStatus
    error: Optional[str] = None


class BulkCreateResponse(BaseModel):
    batch_id: str
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    processing_time_seconds: Optional[float] = None
    batch_activated: bool
    hospitals: List[HospitalResult]


class BatchStatusResponse(BaseModel):
    batch_id: str
    status: BatchStatus
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    processing_time_seconds: Optional[float] = None
    batch_activated: bool
    hospitals: List[HospitalResult]


class CSVValidationError(BaseModel):
    row: int
    error: str


class CSVValidationResponse(BaseModel):
    valid: bool
    total_rows: int
    errors: List[CSVValidationError]
    hospitals: List[dict]


class BatchSummary(BaseModel):
    batch_id: str
    status: BatchStatus
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    batch_activated: bool
    processing_time_seconds: Optional[float] = None


class ResumeResponse(BaseModel):
    batch_id: str
    resumed: bool
    message: str
    skipped_hospitals: int
    hospitals_to_retry: int
