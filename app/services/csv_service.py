import csv
import io
from typing import Tuple
from app.models import HospitalRecord
from app.schemas import CSVValidationError, CSVValidationResponse
from app.config import settings

REQUIRED_FIELDS = {"name", "address"}
OPTIONAL_FIELDS = {"phone"}
ALL_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS


def parse_and_validate_csv(
    content: bytes,
) -> Tuple[list[HospitalRecord], list[CSVValidationError]]:
    text = content.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))

    errors: list[CSVValidationError] = []
    hospitals: list[HospitalRecord] = []

    if reader.fieldnames is None:
        errors.append(CSVValidationError(row=0, error="CSV file is empty or missing headers"))
        return hospitals, errors

    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = REQUIRED_FIELDS - headers
    if missing:
        errors.append(
            CSVValidationError(row=0, error=f"Missing required columns: {', '.join(missing)}")
        )
        return hospitals, errors

    for idx, row in enumerate(reader, start=1):
        normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        row_errors = []

        name = normalized.get("name", "")
        address = normalized.get("address", "")
        phone = normalized.get("phone", "") or None

        if not name:
            row_errors.append(f"'name' is required")
        if not address:
            row_errors.append(f"'address' is required")

        if row_errors:
            errors.append(CSVValidationError(row=idx, error="; ".join(row_errors)))
        else:
            hospitals.append(HospitalRecord(row=idx, name=name, address=address, phone=phone))

    if not errors and len(hospitals) > settings.max_csv_hospitals:
        errors.append(
            CSVValidationError(
                row=0,
                error=f"CSV exceeds maximum limit of {settings.max_csv_hospitals} hospitals (got {len(hospitals)})",
            )
        )
        return [], errors

    return hospitals, errors


def validate_csv_only(content: bytes) -> CSVValidationResponse:
    hospitals, errors = parse_and_validate_csv(content)
    hospital_dicts = [
        {"row": h.row, "name": h.name, "address": h.address, "phone": h.phone}
        for h in hospitals
    ]
    return CSVValidationResponse(
        valid=len(errors) == 0,
        total_rows=len(hospitals),
        errors=errors,
        hospitals=hospital_dicts,
    )
