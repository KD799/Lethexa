
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from urllib.parse import urlparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg import Error as PostgresError

from app.core.security import require_admin
from app.services.s3_pii_scanner import detect_pii
from app.connectors.s3_connector import S3Connector


# Connect to the scanner repository
LATEST_BACKEND = Path(__file__).resolve().parents[3] / "Backend_latest"

if str(LATEST_BACKEND) not in sys.path:
    sys.path.insert(0, str(LATEST_BACKEND))

load_dotenv(LATEST_BACKEND / ".env")

from connectors.config import PostgresConfig
from connectors.postgres import PostgresConnector
from scanner.scan import scan_database
from scanner.locate import locate_subject


router = APIRouter(
    prefix="/discovery",
    tags=["PII Discovery"],
)


class PIIScanRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


class S3ScanRequest(BaseModel):
    bucket_name: str = Field(min_length=3, max_length=255)
    endpoint_url: Optional[str] = "http://127.0.0.1:5000"

    @field_validator("bucket_name")
    @classmethod
    def validate_bucket_name(cls, value):
        value = value.strip()

        if not value or any(char.isspace() for char in value):
            raise ValueError("Invalid bucket name")

        return value

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, value):
        if value is None:
            return value

        parsed = urlparse(value)

        if parsed.scheme not in ("http", "https"):
            raise ValueError("Endpoint must use HTTP or HTTPS")

        if not parsed.hostname:
            raise ValueError("Invalid endpoint URL")

        if parsed.username or parsed.password:
            raise ValueError("Credentials must not be embedded in endpoint URLs")

        return value


class LocateRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    category: Optional[str] = None

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Identifier cannot be empty")

        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value):
        if value is None:
            return value

        value = value.strip().upper()

        if not value:
            return None

        return value


@router.post("/scan")
def scan_pii(
    request: PIIScanRequest,
    current_user=Depends(require_admin),
):
    result = detect_pii(request.text)

    return {
        "module": "CyberShield PII Discovery",
        "scan_status": "completed",
        "result": result,
    }


@router.post("/s3-scan")
def scan_s3_bucket(
    request: S3ScanRequest,
    current_user=Depends(require_admin),
):
    connector = S3Connector(
        endpoint_url=request.endpoint_url
    )

    try:
        files = connector.list_files(request.bucket_name)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    supported_extensions = (
        ".txt", ".csv", ".json", ".log"
    )

    scan_results = []

    for file in files:
        file_name = file["file_name"]

        if not file_name.lower().endswith(supported_extensions):
            scan_results.append({
                "file_name": file_name,
                "scan_status": "skipped",
                "reason": "Unsupported file format",
            })
            continue

        try:
            content = connector.read_file(
                request.bucket_name,
                file_name,
            )

            result = detect_pii(content)

            scan_results.append({
                "file_name": file_name,
                "scan_status": "completed",
                "contains_pii": result["contains_pii"],
                "total_pii_categories": result["total_pii_categories"],
                "findings": result["findings"],
            })

        except ValueError:
            scan_results.append({
                "file_name": file_name,
                "scan_status": "failed",
                "reason": "Unable to read file",
            })

    scanned_files = sum(
        1 for item in scan_results
        if item["scan_status"] == "completed"
    )

    files_with_pii = sum(
        1 for item in scan_results
        if item.get("contains_pii") is True
    )

    return {
        "module": "CyberShield S3 PII Discovery",
        "bucket_name": request.bucket_name,
        "total_files": len(files),
        "scanned_files": scanned_files,
        "files_with_pii": files_with_pii,
        "results": scan_results,
    }


@router.post("/locate")
def locate_pii_subject(
    request: LocateRequest,
    current_user=Depends(require_admin),
):
    try:
        with PostgresConnector(PostgresConfig.from_env()) as db:
            findings = scan_database(db)

            result = locate_subject(
                db=db,
                findings=findings,
                identifier=request.identifier,
                category=request.category,
            )

            return {
                "module": "CyberShield PII Subject Locator",
                "status": "completed",
                "category": result.category,
                "columns_searched": result.columns_searched,
                "total_matching_rows": result.total_rows,
                "matches": [
                    {
                        "table": match.table,
                        "column": match.column,
                        "match_count": match.match_count,
                        "key_columns": match.key_columns,
                        "keys": [
                            list(key) for key in match.keys
                        ],
                    }
                    for match in result.matches
                ],
            }

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except PostgresError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to the PostgreSQL scanning database.",
        )
