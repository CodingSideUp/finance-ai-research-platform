import os

from dotenv import load_dotenv

from src.processing.normalizer import normalize_document
from src.processing.sec_parser import parse_sec_filing
from src.processing.validator import validate_processed_document
from src.storage.gcs_storage import GCSStorage


# =========================================================
# LOAD ENVIRONMENT CONFIGURATION
# =========================================================

load_dotenv()


project_id = os.getenv(
    "GCP_PROJECT_ID"
)

raw_bucket = os.getenv(
    "GCS_RAW_BUCKET"
)


if not project_id:

    raise ValueError(
        "GCP_PROJECT_ID is missing from .env"
    )


if not raw_bucket:

    raise ValueError(
        "GCS_RAW_BUCKET is missing from .env"
    )


# =========================================================
# CONNECT TO GCS RAW BUCKET
# =========================================================

storage = GCSStorage(
    project_id=project_id,
    bucket_name=raw_bucket,
)


# =========================================================
# DISCOVER RAW SEC FILINGS
# =========================================================

objects = storage.list_objects(
    prefix="sec/"
)


filing_objects = [
    path
    for path in objects
    if not path.endswith(
        "manifest.json"
    )
]


if not filing_objects:

    raise RuntimeError(
        "No SEC filing objects were found "
        "inside the RAW bucket."
    )


# =========================================================
# SELECT ONE REAL FILING
# =========================================================

filing_path = filing_objects[0]


base_path = filing_path.rsplit(
    "/",
    1,
)[0]


manifest_path = (
    f"{base_path}/manifest.json"
)


print(
    "\n========================================"
)

print(
    "SEC PROCESSING VALIDATOR SMOKE TEST"
)

print(
    "========================================"
)


print(
    f"\nRAW filing:"
    f"\n{filing_path}"
)


print(
    f"\nManifest:"
    f"\n{manifest_path}"
)


# =========================================================
# DOWNLOAD RAW FILING
# =========================================================

content = storage.download_bytes(
    filing_path
)


print(
    f"\nRaw filing size:"
    f"\n{len(content):,} bytes"
)


# =========================================================
# DOWNLOAD SOURCE MANIFEST
# =========================================================

manifest = storage.download_json(
    manifest_path
)


print(
    "\nDocument metadata:"
)


print(
    f"Document ID: "
    f"{manifest.get('document_id')}"
)


print(
    f"Company: "
    f"{manifest.get('company')}"
)


print(
    f"Form: "
    f"{manifest.get('form')}"
)


print(
    f"Filing date: "
    f"{manifest.get('filing_date')}"
)


# =========================================================
# PARSE RAW FILING
# =========================================================

print(
    "\n----------------------------------------"
)

print(
    "STEP 1: PARSING"
)

print(
    "----------------------------------------"
)


parsed_document = parse_sec_filing(
    content
)


print(
    "Parsing complete."
)


print(
    f"Visible characters: "
    f"{len(parsed_document.get('full_text', '')):,}"
)


print(
    f"Structured blocks: "
    f"{len(parsed_document.get('blocks', [])):,}"
)


# =========================================================
# NORMALIZE PARSED DOCUMENT
# =========================================================

print(
    "\n----------------------------------------"
)

print(
    "STEP 2: NORMALIZATION"
)

print(
    "----------------------------------------"
)


normalized_document = normalize_document(
    parsed_document
)


print(
    "Normalization complete."
)


print(
    f"Normalized characters: "
    f"{len(normalized_document.get('full_text', '')):,}"
)


print(
    f"Normalized blocks: "
    f"{len(normalized_document.get('blocks', [])):,}"
)


print(
    f"Detected sections: "
    f"{len(normalized_document.get('sections', [])):,}"
)


# =========================================================
# VALIDATE PROCESSED DOCUMENT
# =========================================================

print(
    "\n----------------------------------------"
)

print(
    "STEP 3: VALIDATION"
)

print(
    "----------------------------------------"
)


validation_result = (
    validate_processed_document(
        parsed_document=parsed_document,
        normalized_document=normalized_document,
        manifest=manifest,
    )
)


print(
    "Validation complete."
)


# =========================================================
# OVERALL STATUS
# =========================================================

print(
    "\n========================================"
)

print(
    "OVERALL VALIDATION STATUS"
)

print(
    "========================================"
)


status = validation_result[
    "status"
]


print(
    f"\nSTATUS: {status}"
)


# =========================================================
# VALIDATION SUMMARY
# =========================================================

print(
    "\n========================================"
)

print(
    "VALIDATION SUMMARY"
)

print(
    "========================================"
)


summary = validation_result[
    "summary"
]


print(
    f"\nPassed checks: "
    f"{summary['passed_checks']}"
)


print(
    f"Warning checks: "
    f"{summary['warning_checks']}"
)


print(
    f"Failed checks: "
    f"{summary['failed_checks']}"
)


# =========================================================
# DOCUMENT METRICS
# =========================================================

print(
    "\n========================================"
)

print(
    "DOCUMENT QUALITY METRICS"
)

print(
    "========================================"
)


metrics = validation_result[
    "metrics"
]


for key, value in metrics.items():

    if isinstance(
        value,
        int,
    ):

        print(
            f"{key}: {value:,}"
        )

    else:

        print(
            f"{key}: {value}"
        )


# =========================================================
# INDIVIDUAL VALIDATION CHECKS
# =========================================================

print(
    "\n========================================"
)

print(
    "VALIDATION CHECK DETAILS"
)

print(
    "========================================"
)


checks = validation_result[
    "checks"
]


for index, check in enumerate(
    checks,
    start=1,
):

    print(
        f"\n[{index}] "
        f"{check['name']}"
    )

    print(
        f"STATUS: "
        f"{check['status']}"
    )

    print(
        f"MESSAGE: "
        f"{check['message']}"
    )

    print(
        f"VALUE: "
        f"{check['value']}"
    )


# =========================================================
# SHOW ONLY WARNINGS / FAILURES
# =========================================================

print(
    "\n========================================"
)

print(
    "ISSUES REQUIRING ATTENTION"
)

print(
    "========================================"
)


issues = [
    check
    for check in checks
    if check["status"]
    in {
        "WARNING",
        "FAIL",
    }
]


if not issues:

    print(
        "\nNo validation warnings "
        "or failures were detected."
    )


else:

    for issue in issues:

        print(
            f"\n{issue['status']} "
            f"- {issue['name']}"
        )

        print(
            issue["message"]
        )

        print(
            f"Value: "
            f"{issue['value']}"
        )


# =========================================================
# DOWNSTREAM DECISION
# =========================================================

print(
    "\n========================================"
)

print(
    "DOWNSTREAM PROCESSING DECISION"
)

print(
    "========================================"
)


if status == "PASS":

    print(
        "\nPASS"
    )

    print(
        "This document is suitable "
        "for downstream chunking."
    )


elif status == "WARNING":

    print(
        "\nWARNING"
    )

    print(
        "This document may be usable, "
        "but should be reviewed before "
        "large-scale downstream processing."
    )


else:

    print(
        "\nFAIL"
    )

    print(
        "This document should NOT proceed "
        "to chunking."
    )

    print(
        "Keep the RAW source unchanged and "
        "review the parser/normalizer issue."
    )


# =========================================================
# END
# =========================================================

print(
    "\n========================================"
)

print(
    "VALIDATOR SMOKE TEST COMPLETE"
)

print(
    "========================================"
)