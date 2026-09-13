import hashlib
from datetime import datetime, timezone


def calculate_sha256(content: bytes) -> str:
    """
    Calculate the SHA-256 hash of a document.
    """

    return hashlib.sha256(content).hexdigest()


def create_manifest(
    company: str,
    cik: str,
    filing: dict,
    source_url: str,
    content: bytes,
) -> dict:
    """
    Create metadata describing one SEC filing.
    """

    sha256 = calculate_sha256(content)

    document_id = (
        f"sec_"
        f"{cik}_"
        f"{filing['accession_number']}"
    )

    return {
        "document_id": document_id,
        "company": company,
        "cik": cik,
        "form": filing["form"],
        "filing_date": filing["filing_date"],
        "report_date": filing["report_date"],
        "accession_number": filing["accession_number"],
        "primary_document": filing["primary_document"],
        "source_url": source_url,
        "sha256": sha256,
        "ingested_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "pipeline_version": "1.0",
    }