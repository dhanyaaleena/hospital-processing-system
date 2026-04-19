import asyncio
from datetime import datetime, timezone
from typing import Optional
from app.models import BatchState, BatchStatus, HospitalRecord, HospitalStatus
from app.services.hospital_api import hospital_api
from app.schemas import HospitalResult, BulkCreateResponse, BatchStatusResponse

# In-memory store: batch_id -> BatchState
_batch_store: dict[str, BatchState] = {}

# WebSocket connections: batch_id -> list of queues
_ws_queues: dict[str, list[asyncio.Queue]] = {}


def list_batches() -> list[BatchState]:
    return list(reversed(list(_batch_store.values())))


def get_batch(batch_id: str) -> Optional[BatchState]:
    return _batch_store.get(batch_id)


def register_ws_queue(batch_id: str, queue: asyncio.Queue) -> None:
    _ws_queues.setdefault(batch_id, []).append(queue)


def unregister_ws_queue(batch_id: str, queue: asyncio.Queue) -> None:
    if batch_id in _ws_queues:
        _ws_queues[batch_id].discard(queue) if hasattr(_ws_queues[batch_id], "discard") else None
        try:
            _ws_queues[batch_id].remove(queue)
        except ValueError:
            pass


async def _broadcast(batch_id: str, message: dict) -> None:
    for queue in _ws_queues.get(batch_id, []):
        await queue.put(message)


def _build_result(hospital: HospitalRecord) -> HospitalResult:
    return HospitalResult(
        row=hospital.row,
        hospital_id=hospital.hospital_id,
        name=hospital.name,
        status=hospital.status,
        error=hospital.error,
    )


def _batch_to_status_response(batch: BatchState) -> BatchStatusResponse:
    return BatchStatusResponse(
        batch_id=batch.batch_id,
        status=batch.status,
        total_hospitals=batch.total,
        processed_hospitals=batch.processed,
        failed_hospitals=batch.failed,
        processing_time_seconds=batch.processing_time_seconds,
        batch_activated=batch.batch_activated,
        hospitals=[_build_result(h) for h in batch.hospitals],
    )


async def _create_one(
    hospital: HospitalRecord, batch: BatchState, fail_rows: set[int]
) -> None:
    if hospital.status in (HospitalStatus.created, HospitalStatus.created_and_activated):
        batch.processed += 1
        return
    if hospital.row in fail_rows:
        hospital.status = HospitalStatus.failed
        hospital.error = "Simulated failure (test mode)"
        batch.failed += 1
    else:
        try:
            result = await hospital_api.create_hospital(
                name=hospital.name,
                address=hospital.address,
                batch_id=batch.batch_id,
                phone=hospital.phone,
            )
            hospital.hospital_id = result.get("id")
            hospital.status = HospitalStatus.created
            batch.processed += 1
        except Exception as exc:
            hospital.status = HospitalStatus.failed
            hospital.error = str(exc)
            batch.failed += 1

    await _broadcast(
        batch.batch_id,
        {
            "event": "progress",
            "row": hospital.row,
            "processed": batch.processed,
            "failed": batch.failed,
            "total": batch.total,
            "hospital_status": hospital.status,
        },
    )


async def process_batch(batch: BatchState) -> None:
    batch.status = BatchStatus.processing
    batch.started_at = datetime.now(timezone.utc)
    _batch_store[batch.batch_id] = batch

    await _broadcast(batch.batch_id, {"event": "started", "batch_id": batch.batch_id})

    # Process all hospitals concurrently
    await asyncio.gather(*[_create_one(h, batch, batch.fail_rows) for h in batch.hospitals])

    # Activate batch only if at least one hospital was created
    created_count = sum(
        1 for h in batch.hospitals
        if h.status in (HospitalStatus.created, HospitalStatus.created_and_activated)
    )
    if created_count > 0:
        try:
            await hospital_api.activate_batch(batch.batch_id)
            batch.batch_activated = True
            for hospital in batch.hospitals:
                if hospital.status == HospitalStatus.created:
                    hospital.status = HospitalStatus.created_and_activated
        except Exception as exc:
            batch.error = f"Activation failed: {exc}"

    batch.completed_at = datetime.now(timezone.utc)
    if batch.failed == 0:
        batch.status = BatchStatus.completed
    elif batch.processed > 0:
        batch.status = BatchStatus.partial
    else:
        batch.status = BatchStatus.failed

    await _broadcast(
        batch.batch_id,
        {
            "event": "completed",
            "status": batch.status,
            "batch_activated": batch.batch_activated,
            "processed": batch.processed,
            "failed": batch.failed,
        },
    )


async def start_batch(
    batch_id: str, hospitals: list[HospitalRecord], fail_rows: set[int] = None
) -> BatchState:
    batch = BatchState(batch_id=batch_id, hospitals=hospitals, fail_rows=fail_rows or set())
    _batch_store[batch_id] = batch
    asyncio.create_task(process_batch(batch))
    return batch


async def resume_batch(batch: BatchState) -> tuple[int, int]:
    """Reset failed hospitals and reprocess. Returns (skipped, to_retry)."""
    skipped = sum(
        1 for h in batch.hospitals
        if h.status in (HospitalStatus.created, HospitalStatus.created_and_activated)
    )
    to_retry = sum(1 for h in batch.hospitals if h.status == HospitalStatus.failed)

    for hospital in batch.hospitals:
        if hospital.status == HospitalStatus.failed:
            hospital.status = HospitalStatus.failed  # will be retried
            hospital.error = None

    # Reset counters for failed ones
    batch.processed = skipped
    batch.failed = 0
    batch.batch_activated = False
    batch.completed_at = None

    asyncio.create_task(process_batch(batch))
    return skipped, to_retry
