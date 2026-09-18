import csv
import json
import os
import time

from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

from src.processing.normalizer import normalize_document
from src.processing.sec_parser import parse_sec_filing
from src.processing.validator import validate_processed_document
from src.storage.gcs_storage import GCSStorage


# =========================================================
# CONFIGURATION
# =========================================================

GOLDEN_SAMPLE_PATH = (
    "reports/golden_sample.csv"
)

JSON_REPORT_PATH = (
    "reports/golden_processing_validation.json"
)

CSV_REPORT_PATH = (
    "reports/golden_processing_validation.csv"
)


# =========================================================
# LOAD GOLDEN SAMPLE
# =========================================================

def load_golden_sample(
    path: str,
) -> list[dict]:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(
            file
        )

        return list(
            reader
        )


# =========================================================
# MANIFEST PATH
# =========================================================

def get_manifest_path(
    filing_path: str,
) -> str:

    parent = filing_path.rsplit(
        "/",
        1,
    )[0]

    return (
        f"{parent}/manifest.json"
    )


# =========================================================
# SAFE AVERAGE
# =========================================================

def safe_average(
    values: list,
) -> float:

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


# =========================================================
# MAIN
# =========================================================

def main():

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


    # =====================================================
    # LOAD GOLDEN SET
    # =====================================================

    golden_documents = (
        load_golden_sample(
            GOLDEN_SAMPLE_PATH
        )
    )


    if not golden_documents:

        raise RuntimeError(
            "Golden sample is empty."
        )


    # =====================================================
    # CONNECT TO RAW GCS
    # =====================================================

    storage = GCSStorage(
        project_id=project_id,
        bucket_name=raw_bucket,
    )


    print(
        "\n========================================"
    )

    print(
        "GOLDEN CORPUS PROCESSING BASELINE"
    )

    print(
        "========================================"
    )


    print(
        f"\nDocuments: "
        f"{len(golden_documents)}"
    )


    # =====================================================
    # RESULT CONTAINERS
    # =====================================================

    results = []


    status_counter = Counter()

    risk_status = defaultdict(
        Counter
    )

    form_status = defaultdict(
        Counter
    )

    archetype_status = defaultdict(
        Counter
    )


    parsed_characters = []

    normalized_characters = []

    section_counts = []

    heading_counts = []

    text_retention_ratios = []


    exception_count = 0


    start_time = (
        time.perf_counter()
    )


    # =====================================================
    # PROCESS GOLDEN DOCUMENTS
    # =====================================================

    for index, golden_row in enumerate(
        golden_documents,
        start=1,
    ):

        document_start = (
            time.perf_counter()
        )


        filing_path = (
            golden_row[
                "filing_path"
            ]
        )


        manifest_path = (
            get_manifest_path(
                filing_path
            )
        )


        expected_document_id = (
            golden_row.get(
                "document_id"
            )
        )


        risk = (
            golden_row.get(
                "current_parser_risk"
            )
            or
            "unknown"
        )


        archetype = (
            golden_row.get(
                "parser_archetype"
            )
            or
            "unknown"
        )


        expected_form = (
            golden_row.get(
                "form"
            )
            or
            "unknown"
        )


        print(
            f"\n[{index}/"
            f"{len(golden_documents)}] "
            f"{expected_document_id}"
        )


        try:

            # =============================================
            # DOWNLOAD
            # =============================================

            content = (
                storage.download_bytes(
                    filing_path
                )
            )


            manifest = (
                storage.download_json(
                    manifest_path
                )
            )


            # =============================================
            # PARSE
            # =============================================

            parsed_document = (
                parse_sec_filing(
                    content
                )
            )


            # =============================================
            # NORMALIZE
            # =============================================

            normalized_document = (
                normalize_document(
                    parsed_document
                )
            )


            # =============================================
            # VALIDATE
            # =============================================

            validation = (
                validate_processed_document(
                    parsed_document=(
                        parsed_document
                    ),
                    normalized_document=(
                        normalized_document
                    ),
                    manifest=manifest,
                )
            )


            status = validation[
                "status"
            ]


            metrics = validation[
                "metrics"
            ]


            # =============================================
            # RETENTION
            # =============================================

            parsed_chars = (
                metrics[
                    "parsed_characters"
                ]
            )


            normalized_chars = (
                metrics[
                    "normalized_characters"
                ]
            )


            if parsed_chars > 0:

                retention_ratio = (
                    normalized_chars
                    /
                    parsed_chars
                )

            else:

                retention_ratio = 0.0


            # =============================================
            # ISSUES
            # =============================================

            issues = [
                check
                for check in validation[
                    "checks"
                ]
                if check[
                    "status"
                ]
                in {
                    "WARNING",
                    "FAIL",
                }
            ]


            elapsed = (
                time.perf_counter()
                -
                document_start
            )


            result = {
                "selection_order": (
                    golden_row.get(
                        "selection_order"
                    )
                ),

                "document_id": (
                    manifest.get(
                        "document_id"
                    )
                ),

                "company": (
                    manifest.get(
                        "company"
                    )
                ),

                "cik": (
                    manifest.get(
                        "cik"
                    )
                ),

                "form": (
                    manifest.get(
                        "form"
                    )
                ),

                "filing_path": (
                    filing_path
                ),

                "parser_risk": (
                    risk
                ),

                "parser_archetype": (
                    archetype
                ),

                "structural_family": (
                    golden_row.get(
                        "structural_family"
                    )
                ),

                "status": (
                    status
                ),

                "parsed_characters": (
                    parsed_chars
                ),

                "normalized_characters": (
                    normalized_chars
                ),

                "sections": (
                    metrics[
                        "sections"
                    ]
                ),

                "headings": (
                    metrics[
                        "headings"
                    ]
                ),

                "tables": (
                    metrics[
                        "tables"
                    ]
                ),

                "text_retention_ratio": round(
                    retention_ratio,
                    6,
                ),

                "elapsed_seconds": round(
                    elapsed,
                    4,
                ),

                "issues": (
                    issues
                ),
            }


            # =============================================
            # AGGREGATE METRICS
            # =============================================

            parsed_characters.append(
                parsed_chars
            )


            normalized_characters.append(
                normalized_chars
            )


            section_counts.append(
                metrics[
                    "sections"
                ]
            )


            heading_counts.append(
                metrics[
                    "headings"
                ]
            )


            text_retention_ratios.append(
                retention_ratio
            )


            print(
                f"  Status: "
                f"{status}"
            )

            print(
                f"  Sections: "
                f"{metrics['sections']}"
            )

            print(
                f"  Headings: "
                f"{metrics['headings']}"
            )


        except Exception as error:

            exception_count += 1

            status = "FAIL"


            elapsed = (
                time.perf_counter()
                -
                document_start
            )


            result = {
                "selection_order": (
                    golden_row.get(
                        "selection_order"
                    )
                ),

                "document_id": (
                    expected_document_id
                ),

                "company": (
                    golden_row.get(
                        "company"
                    )
                ),

                "cik": (
                    golden_row.get(
                        "cik"
                    )
                ),

                "form": (
                    expected_form
                ),

                "filing_path": (
                    filing_path
                ),

                "parser_risk": (
                    risk
                ),

                "parser_archetype": (
                    archetype
                ),

                "structural_family": (
                    golden_row.get(
                        "structural_family"
                    )
                ),

                "status": "FAIL",

                "error_type": (
                    type(error).__name__
                ),

                "error_message": (
                    str(error)
                ),

                "elapsed_seconds": round(
                    elapsed,
                    4,
                ),
            }


            print(
                "  Status: FAIL"
            )

            print(
                f"  Error: "
                f"{error}"
            )


        # =================================================
        # STATUS COUNTERS
        # =================================================

        status_counter[
            status
        ] += 1


        risk_status[
            risk
        ][
            status
        ] += 1


        form_status[
            expected_form
        ][
            status
        ] += 1


        archetype_status[
            archetype
        ][
            status
        ] += 1


        results.append(
            result
        )


    # =====================================================
    # FINAL METRICS
    # =====================================================

    elapsed = (
        time.perf_counter()
        -
        start_time
    )


    total = len(
        results
    )


    passed = status_counter[
        "PASS"
    ]


    warning = status_counter[
        "WARNING"
    ]


    failed = status_counter[
        "FAIL"
    ]


    pass_rate = (
        passed
        /
        total
        if total
        else 0
    )


    # =====================================================
    # PRINT BASELINE
    # =====================================================

    print(
        "\n\n========================================"
    )

    print(
        "GOLDEN BASELINE SUMMARY"
    )

    print(
        "========================================"
    )


    print(
        f"\nDocuments: "
        f"{total}"
    )

    print(
        f"PASS: "
        f"{passed}"
    )

    print(
        f"WARNING: "
        f"{warning}"
    )

    print(
        f"FAIL: "
        f"{failed}"
    )

    print(
        f"Exceptions: "
        f"{exception_count}"
    )

    print(
        f"\nPASS rate: "
        f"{pass_rate:.2%}"
    )


    print(
        "\nAverage metrics:"
    )

    print(
        f"  Sections: "
        f"{safe_average(section_counts):.2f}"
    )

    print(
        f"  Headings: "
        f"{safe_average(heading_counts):.2f}"
    )

    print(
        f"  Text retention: "
        f"{safe_average(text_retention_ratios):.2%}"
    )


    # =====================================================
    # RESULTS BY RISK
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "RESULTS BY PARSER RISK"
    )

    print(
        "========================================"
    )


    for risk_name in sorted(
        risk_status.keys()
    ):

        stats = risk_status[
            risk_name
        ]


        print(
            f"\n{risk_name}"
        )

        print(
            f"  PASS: "
            f"{stats['PASS']}"
        )

        print(
            f"  WARNING: "
            f"{stats['WARNING']}"
        )

        print(
            f"  FAIL: "
            f"{stats['FAIL']}"
        )


    # =====================================================
    # RESULTS BY FORM
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "RESULTS BY FORM"
    )

    print(
        "========================================"
    )


    for form_name in sorted(
        form_status.keys()
    ):

        stats = form_status[
            form_name
        ]


        print(
            f"\n{form_name}"
        )

        print(
            f"  PASS: "
            f"{stats['PASS']}"
        )

        print(
            f"  WARNING: "
            f"{stats['WARNING']}"
        )

        print(
            f"  FAIL: "
            f"{stats['FAIL']}"
        )


    # =====================================================
    # SAVE JSON
    # =====================================================

    report = {
        "summary": {
            "documents": (
                total
            ),

            "pass": (
                passed
            ),

            "warning": (
                warning
            ),

            "fail": (
                failed
            ),

            "exceptions": (
                exception_count
            ),

            "pass_rate": round(
                pass_rate,
                6,
            ),

            "average_sections": round(
                safe_average(
                    section_counts
                ),
                4,
            ),

            "average_headings": round(
                safe_average(
                    heading_counts
                ),
                4,
            ),

            "average_text_retention": round(
                safe_average(
                    text_retention_ratios
                ),
                6,
            ),

            "elapsed_seconds": round(
                elapsed,
                2,
            ),
        },

        "risk_results": {
            key: dict(
                value
            )
            for key, value in (
                risk_status.items()
            )
        },

        "form_results": {
            key: dict(
                value
            )
            for key, value in (
                form_status.items()
            )
        },

        "archetype_results": {
            key: dict(
                value
            )
            for key, value in (
                archetype_status.items()
            )
        },

        "documents": (
            results
        ),
    }


    json_path = Path(
        JSON_REPORT_PATH
    )


    json_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )


    # =====================================================
    # SAVE CSV
    # =====================================================

    csv_path = Path(
        CSV_REPORT_PATH
    )


    csv_rows = []


    for result in results:

        csv_row = {
            key: value
            for key, value in (
                result.items()
            )
            if key != "issues"
        }


        issues = result.get(
            "issues",
            []
        )


        csv_row[
            "issue_names"
        ] = "; ".join(
            issue[
                "name"
            ]
            for issue in issues
        )


        csv_rows.append(
            csv_row
        )


    if csv_rows:

        all_fields = []

        seen_fields = set()


        for row in csv_rows:

            for field in row.keys():

                if field not in seen_fields:

                    seen_fields.add(
                        field
                    )

                    all_fields.append(
                        field
                    )


        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=(
                    all_fields
                ),
                extrasaction="ignore",
            )


            writer.writeheader()


            writer.writerows(
                csv_rows
            )


    # =====================================================
    # DONE
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "BASELINE REPORTS SAVED"
    )

    print(
        "========================================"
    )


    print(
        f"\n{JSON_REPORT_PATH}"
    )

    print(
        CSV_REPORT_PATH
    )

    print(
        f"\nElapsed: "
        f"{elapsed:.2f} seconds"
    )


if __name__ == "__main__":
    main()