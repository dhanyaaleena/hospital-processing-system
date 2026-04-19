import asyncio
import uuid
from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from app.schemas import (
    BulkCreateResponse,
    BatchStatusResponse,
    BatchSummary,
    CSVValidationResponse,
    HospitalResult,
    ResumeResponse,
)
from app.models import BatchStatus, HospitalStatus
from app.services.csv_service import parse_and_validate_csv, validate_csv_only
from app.services.batch_service import (
    get_batch,
    list_batches,
    register_ws_queue,
    start_batch,
    unregister_ws_queue,
    resume_batch,
    _batch_to_status_response,
)

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.post("/bulk", response_model=BulkCreateResponse, status_code=202)
async def bulk_create_hospitals(
    file: UploadFile = File(...),
    simulate_fail_rows: str = "",
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    hospitals, errors = parse_and_validate_csv(content)

    if errors:
        raise HTTPException(
            status_code=422,
            detail=[{"row": e.row, "error": e.error} for e in errors],
        )

    # Parse comma-separated row numbers to simulate failures (e.g. "2,4,5")
    fail_rows: set[int] = set()
    if simulate_fail_rows:
        try:
            fail_rows = {int(r.strip()) for r in simulate_fail_rows.split(",") if r.strip()}
        except ValueError:
            pass

    batch_id = str(uuid.uuid4())
    batch = await start_batch(batch_id, hospitals, fail_rows=fail_rows)

    # Return immediately — processing runs in the background
    return BulkCreateResponse(
        batch_id=batch.batch_id,
        total_hospitals=batch.total,
        processed_hospitals=batch.processed,
        failed_hospitals=batch.failed,
        processing_time_seconds=batch.processing_time_seconds,
        batch_activated=batch.batch_activated,
        hospitals=[
            HospitalResult(
                row=h.row,
                hospital_id=h.hospital_id,
                name=h.name,
                status=h.status,
                error=h.error,
            )
            for h in batch.hospitals
        ],
    )


@router.get("/bulk", response_model=list[BatchSummary])
async def list_all_batches():
    return [
        BatchSummary(
            batch_id=b.batch_id,
            status=b.status,
            total_hospitals=b.total,
            processed_hospitals=b.processed,
            failed_hospitals=b.failed,
            batch_activated=b.batch_activated,
            processing_time_seconds=b.processing_time_seconds,
        )
        for b in list_batches()
    ]


@router.get("/bulk/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return _batch_to_status_response(batch)


@router.post("/bulk/validate", response_model=CSVValidationResponse)
async def validate_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    content = await file.read()
    return validate_csv_only(content)


@router.post("/bulk/{batch_id}/resume", response_model=ResumeResponse)
async def resume_failed_batch(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")

    if batch.status == BatchStatus.processing:
        raise HTTPException(status_code=409, detail="Batch is currently processing")

    if batch.status == BatchStatus.completed:
        raise HTTPException(status_code=409, detail="Batch already completed successfully")

    failed_count = sum(1 for h in batch.hospitals if h.status == HospitalStatus.failed)
    if failed_count == 0:
        raise HTTPException(status_code=409, detail="No failed hospitals to retry")

    skipped, to_retry = await resume_batch(batch)

    return ResumeResponse(
        batch_id=batch_id,
        resumed=True,
        message=f"Resuming batch: retrying {to_retry} failed hospital(s), skipping {skipped} already processed",
        skipped_hospitals=skipped,
        hospitals_to_retry=to_retry,
    )


@router.websocket("/bulk/{batch_id}/ws")
async def batch_progress_ws(websocket: WebSocket, batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    register_ws_queue(batch_id, queue)

    def _completed_event():
        return {
            "event": "completed",
            "status": batch.status,
            "batch_activated": batch.batch_activated,
            "processed": batch.processed,
            "failed": batch.failed,
        }

    try:
        await websocket.send_json(
            {
                "event": "state",
                "batch_id": batch_id,
                "status": batch.status,
                "processed": batch.processed,
                "failed": batch.failed,
                "total": batch.total,
            }
        )

        # Already finished before WS connected — send synthetic completed and exit
        if batch.status not in (BatchStatus.pending, BatchStatus.processing):
            await websocket.send_json(_completed_event())
            return

        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json(msg)
                if msg.get("event") == "completed":
                    break
            except asyncio.TimeoutError:
                # Batch finished while we were waiting with nothing queued
                if batch.status not in (BatchStatus.pending, BatchStatus.processing):
                    await websocket.send_json(_completed_event())
                    break

    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws_queue(batch_id, queue)
        await websocket.close()
