import pytest
from app.services.csv_service import parse_and_validate_csv, validate_csv_only


def csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


def test_valid_csv_with_phone():
    content = csv_bytes("name,address,phone\nGeneral Hospital,123 Main St,555-1234")
    hospitals, errors = parse_and_validate_csv(content)
    assert len(errors) == 0
    assert len(hospitals) == 1
    assert hospitals[0].name == "General Hospital"
    assert hospitals[0].phone == "555-1234"


def test_valid_csv_without_phone():
    content = csv_bytes("name,address\nCity Clinic,456 Elm Ave")
    hospitals, errors = parse_and_validate_csv(content)
    assert len(errors) == 0
    assert len(hospitals) == 1
    assert hospitals[0].phone is None


def test_missing_required_column():
    content = csv_bytes("name,phone\nCity Clinic,555-0000")
    hospitals, errors = parse_and_validate_csv(content)
    assert any("address" in e.error for e in errors)
    assert len(hospitals) == 0


def test_missing_name_value():
    content = csv_bytes("name,address\n,456 Elm Ave")
    hospitals, errors = parse_and_validate_csv(content)
    assert any("name" in e.error for e in errors)


def test_missing_address_value():
    content = csv_bytes("name,address\nCity Clinic,")
    hospitals, errors = parse_and_validate_csv(content)
    assert any("address" in e.error for e in errors)


def test_exceeds_max_hospitals():
    rows = "\n".join(f"Hospital {i},Address {i}" for i in range(1, 22))
    content = csv_bytes(f"name,address\n{rows}")
    hospitals, errors = parse_and_validate_csv(content)
    assert any("maximum limit" in e.error for e in errors)
    assert len(hospitals) == 0


def test_multiple_hospitals():
    content = csv_bytes(
        "name,address,phone\n"
        "Hospital A,100 A St,111-1111\n"
        "Hospital B,200 B Ave,222-2222\n"
        "Hospital C,300 C Blvd,"
    )
    hospitals, errors = parse_and_validate_csv(content)
    assert len(errors) == 0
    assert len(hospitals) == 3
    assert hospitals[2].phone is None


def test_validate_csv_only_valid():
    content = csv_bytes("name,address\nHospital X,1 X Rd")
    result = validate_csv_only(content)
    assert result.valid is True
    assert result.total_rows == 1
    assert len(result.errors) == 0


def test_validate_csv_only_invalid():
    content = csv_bytes("name\nHospital X")
    result = validate_csv_only(content)
    assert result.valid is False
    assert len(result.errors) > 0


def test_bom_handling():
    # Simulate a UTF-8 BOM file (Excel CSV export)
    content = "name,address\nBOM Hospital,1 BOM St".encode("utf-8-sig")
    hospitals, errors = parse_and_validate_csv(content)
    assert len(errors) == 0
    assert hospitals[0].name == "BOM Hospital"


def test_row_numbers_are_correct():
    content = csv_bytes(
        "name,address\n"
        "H1,A1\n"
        "H2,A2\n"
        "H3,A3"
    )
    hospitals, _ = parse_and_validate_csv(content)
    assert [h.row for h in hospitals] == [1, 2, 3]
