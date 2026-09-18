import argparse
import json
import os
import random
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from src.processing.normalizer import normalize_document
from src.processing.sec_parser import parse_sec_filing
from src.processing.validator import validate_processed_document
from src.storage.gcs_storage import GCSStorage


# =========================================================
# COMMAND-LINE ARGUMENTS
# =========================================================

def parse_arguments():
    """
    Configuration for the batch validation run.

    Example:

        python -m scripts.test_processing_batch \
            --sample-size 100 \
            --seed 42
    """

    parser = argparse.ArgumentParser(
        description=(
            "Validate SEC parsing and normalization "
            "across a representative batch of filings."
        )
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help=(
            "Number of SEC filings to validate. "
            "Default: 100"
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help=(
            "Random seed used to make the document "
            "sample reproducible. Default: 42"
        ),
    )

    parser.add_argument(
        "--required-pass-rate",
        type=float,
        default=0.95,
        help=(
            "Project quality gate for PASS documents. "
            "Default: 0.95"
        ),
    )

    parser.add_argument(
        "--report-path",
        type=str,
        default=(
            "reports/"
            "processing_batch_validation.json"
        ),
        help=(
            "Local JSON path for the validation report."
        ),
    )

    return parser.parse_args()


# =========================================================
# HELPER: SAFE AVERAGE
# =========================================================

def safe_average(
    values: list,
) -> float:
    """
    Return the arithmetic average.

    If no values exist, return 0.
    """

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


# =========================================================
# HELPER: MANIFEST PATH
# =========================================================

def get_manifest_path(
    filing_path: str,
) -> str:
    """
    Convert:

        sec/CIK/accession/file.htm

    into:

        sec/CIK/accession/manifest.json
    """

    base_path = filing_path.rsplit(
        "/",
        1,
    )[0]

    return (
        f"{base_path}/manifest.json"
    )


# =========================================================
# HELPER: INITIALIZE FORM STATISTICS
# =========================================================

def create_form_statistics():
    """
    Statistics maintained separately for
    10-K, 10-Q, or any unexpected form.
    """

    return {
        "attempted": 0,
        "PASS": 0,
        "WARNING": 0,
        "FAIL": 0,
    }


# =========================================================
# MAIN
# =========================================================

def main():

    # =====================================================
    # LOAD CONFIGURATION
    # =====================================================

    args = parse_arguments()

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


    if args.sample_size <= 0:

        raise ValueError(
            "sample-size must be greater than zero."
        )


    if not (
        0
        <= args.required_pass_rate
        <= 1
    ):

        raise ValueError(
            "required-pass-rate must be "
            "between 0 and 1."
        )


    # =====================================================
    # CONNECT TO GCS
    # =====================================================

    storage = GCSStorage(
        project_id=project_id,
        bucket_name=raw_bucket,
    )


    # =====================================================
    # DISCOVER RAW SEC FILINGS
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "SEC BATCH PROCESSING VALIDATION"
    )

    print(
        "========================================"
    )


    print(
        "\nDiscovering RAW SEC filings..."
    )


    objects = storage.list_objects(
        prefix="sec/"
    )


    filing_objects = sorted(
        [
            path
            for path in objects
            if not path.endswith(
                "manifest.json"
            )
        ]
    )


    if not filing_objects:

        raise RuntimeError(
            "No SEC filings were found "
            "in the RAW bucket."
        )


    corpus_size = len(
        filing_objects
    )


    sample_size = min(
        args.sample_size,
        corpus_size,
    )


    print(
        f"\nRAW corpus filings: "
        f"{corpus_size:,}"
    )

    print(
        f"Validation sample: "
        f"{sample_size:,}"
    )

    print(
        f"Random seed: "
        f"{args.seed}"
    )


    # =====================================================
    # CREATE REPRODUCIBLE RANDOM SAMPLE
    # =====================================================

    random_generator = random.Random(
        args.seed
    )


    selected_filings = (
        random_generator.sample(
            filing_objects,
            sample_size,
        )
    )


    # =====================================================
    # BATCH METRICS
    # =====================================================

    batch_start = time.perf_counter()


    status_counts = {
        "PASS": 0,
        "WARNING": 0,
        "FAIL": 0,
    }


    form_statistics = defaultdict(
        create_form_statistics
    )


    parsed_character_values = []

    normalized_character_values = []

    parsed_block_values = []

    normalized_block_values = []

    section_values = []

    heading_values = []

    table_values = []

    text_retention_values = []


    exception_count = 0


    results = []


    # =====================================================
    # PROCESS EACH SELECTED DOCUMENT
    # =====================================================

    for position, filing_path in enumerate(
        selected_filings,
        start=1,
    ):

        document_start = (
            time.perf_counter()
        )


        manifest_path = (
            get_manifest_path(
                filing_path
            )
        )


        # Defaults used if processing fails before
        # manifest information becomes available.
        document_id = None

        company = None

        form = "UNKNOWN"


        print(
            "\n----------------------------------------"
        )

        print(
            f"[{position}/{sample_size}]"
        )

        print(
            filing_path
        )


        try:

            # =============================================
            # DOWNLOAD RAW SOURCE + MANIFEST
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


            document_id = manifest.get(
                "document_id"
            )

            company = manifest.get(
                "company"
            )

            form = (
                manifest.get(
                    "form"
                )
                or
                "UNKNOWN"
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

            validation_result = (
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


            status = validation_result[
                "status"
            ]


            metrics = validation_result[
                "metrics"
            ]


            # =============================================
            # TEXT RETENTION
            # =============================================

            parsed_characters = (
                metrics[
                    "parsed_characters"
                ]
            )


            normalized_characters = (
                metrics[
                    "normalized_characters"
                ]
            )


            if parsed_characters > 0:

                text_retention_ratio = (
                    normalized_characters
                    /
                    parsed_characters
                )

            else:

                text_retention_ratio = 0.0


            # =============================================
            # AGGREGATE METRICS
            # =============================================

            parsed_character_values.append(
                parsed_characters
            )


            normalized_character_values.append(
                normalized_characters
            )


            parsed_block_values.append(
                metrics[
                    "parsed_blocks"
                ]
            )


            normalized_block_values.append(
                metrics[
                    "normalized_blocks"
                ]
            )


            section_values.append(
                metrics[
                    "sections"
                ]
            )


            heading_values.append(
                metrics[
                    "headings"
                ]
            )


            table_values.append(
                metrics[
                    "tables"
                ]
            )


            text_retention_values.append(
                text_retention_ratio
            )


            # =============================================
            # SAVE DOCUMENT RESULT
            # =============================================

            issues = [
                check
                for check in (
                    validation_result[
                        "checks"
                    ]
                )
                if check["status"]
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
                "filing_path": filing_path,
                "manifest_path": (
                    manifest_path
                ),
                "document_id": (
                    document_id
                ),
                "company": company,
                "form": form,
                "status": status,
                "elapsed_seconds": round(
                    elapsed,
                    4,
                ),
                "metrics": metrics,
                "text_retention_ratio": round(
                    text_retention_ratio,
                    4,
                ),
                "issues": issues,
            }


            print(
                f"Company: {company}"
            )

            print(
                f"Form: {form}"
            )

            print(
                f"Status: {status}"
            )

            print(
                f"Parsed chars: "
                f"{parsed_characters:,}"
            )

            print(
                f"Normalized chars: "
                f"{normalized_characters:,}"
            )

            print(
                f"Sections: "
                f"{metrics['sections']}"
            )


        except Exception as error:

            # =============================================
            # FAILURE ISOLATION
            # =============================================
            #
            # One document failure is recorded,
            # but the rest of the batch continues.
            # =============================================

            status = "FAIL"

            exception_count += 1


            elapsed = (
                time.perf_counter()
                -
                document_start
            )


            result = {
                "filing_path": filing_path,
                "manifest_path": (
                    manifest_path
                ),
                "document_id": (
                    document_id
                ),
                "company": company,
                "form": form,
                "status": "FAIL",
                "elapsed_seconds": round(
                    elapsed,
                    4,
                ),
                "error_type": (
                    type(error).__name__
                ),
                "error_message": str(
                    error
                ),
            }


            print(
                "Status: FAIL"
            )

            print(
                f"Error type: "
                f"{type(error).__name__}"
            )

            print(
                f"Error: {error}"
            )


        # =================================================
        # UPDATE STATUS COUNTERS
        # =================================================

        status_counts[
            status
        ] += 1


        form_statistics[
            form
        ][
            "attempted"
        ] += 1


        form_statistics[
            form
        ][
            status
        ] += 1


        results.append(
            result
        )


    # =====================================================
    # FINAL BATCH METRICS
    # =====================================================

    batch_elapsed = (
        time.perf_counter()
        -
        batch_start
    )


    attempted = len(
        results
    )


    passed = status_counts[
        "PASS"
    ]

    warnings = status_counts[
        "WARNING"
    ]

    failed = status_counts[
        "FAIL"
    ]


    pass_rate = (
        passed
        /
        attempted
        if attempted
        else 0
    )


    warning_rate = (
        warnings
        /
        attempted
        if attempted
        else 0
    )


    failure_rate = (
        failed
        /
        attempted
        if attempted
        else 0
    )


    # =====================================================
    # QUALITY GATE
    # =====================================================

    if (
        pass_rate
        >=
        args.required_pass_rate
    ):

        quality_gate = "PASS"

    else:

        quality_gate = "FAIL"


    # =====================================================
    # PRINT CORPUS-LEVEL REPORT
    # =====================================================

    print(
        "\n\n========================================"
    )

    print(
        "BATCH VALIDATION SUMMARY"
    )

    print(
        "========================================"
    )


    print(
        f"\nDocuments attempted: "
        f"{attempted:,}"
    )

    print(
        f"PASS: "
        f"{passed:,}"
    )

    print(
        f"WARNING: "
        f"{warnings:,}"
    )

    print(
        f"FAIL: "
        f"{failed:,}"
    )

    print(
        f"Exceptions: "
        f"{exception_count:,}"
    )


    print(
        f"\nPass rate: "
        f"{pass_rate:.2%}"
    )

    print(
        f"Warning rate: "
        f"{warning_rate:.2%}"
    )

    print(
        f"Failure rate: "
        f"{failure_rate:.2%}"
    )


    print(
        "\n========================================"
    )

    print(
        "AVERAGE DOCUMENT METRICS"
    )

    print(
        "========================================"
    )


    print(
        f"\nParsed characters: "
        f"{safe_average(parsed_character_values):,.2f}"
    )

    print(
        f"Normalized characters: "
        f"{safe_average(normalized_character_values):,.2f}"
    )

    print(
        f"Parsed blocks: "
        f"{safe_average(parsed_block_values):,.2f}"
    )

    print(
        f"Normalized blocks: "
        f"{safe_average(normalized_block_values):,.2f}"
    )

    print(
        f"Sections: "
        f"{safe_average(section_values):,.2f}"
    )

    print(
        f"Headings: "
        f"{safe_average(heading_values):,.2f}"
    )

    print(
        f"Tables: "
        f"{safe_average(table_values):,.2f}"
    )

    print(
        f"Text retention: "
        f"{safe_average(text_retention_values):.2%}"
    )


    # =====================================================
    # FORM-LEVEL RESULTS
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "RESULTS BY SEC FORM"
    )

    print(
        "========================================"
    )


    for form_name in sorted(
        form_statistics.keys()
    ):

        stats = form_statistics[
            form_name
        ]


        print(
            f"\n{form_name}"
        )

        print(
            f"Attempted: "
            f"{stats['attempted']}"
        )

        print(
            f"PASS: "
            f"{stats['PASS']}"
        )

        print(
            f"WARNING: "
            f"{stats['WARNING']}"
        )

        print(
            f"FAIL: "
            f"{stats['FAIL']}"
        )


    # =====================================================
    # WARNING / FAILURE DOCUMENTS
    # =====================================================

    problem_documents = [
        result
        for result in results
        if result[
            "status"
        ]
        in {
            "WARNING",
            "FAIL",
        }
    ]


    print(
        "\n========================================"
    )

    print(
        "DOCUMENTS REQUIRING REVIEW"
    )

    print(
        "========================================"
    )


    if not problem_documents:

        print(
            "\nNo WARNING or FAIL documents."
        )


    else:

        for result in problem_documents:

            print(
                "\n----------------------------------------"
            )

            print(
                f"Status: "
                f"{result['status']}"
            )

            print(
                f"Document ID: "
                f"{result.get('document_id')}"
            )

            print(
                f"Company: "
                f"{result.get('company')}"
            )

            print(
                f"Form: "
                f"{result.get('form')}"
            )

            print(
                f"Path: "
                f"{result['filing_path']}"
            )


            if "error_type" in result:

                print(
                    f"Error type: "
                    f"{result['error_type']}"
                )

                print(
                    f"Error: "
                    f"{result['error_message']}"
                )


            else:

                for issue in result.get(
                    "issues",
                    [],
                ):

                    print(
                        f"{issue['status']} "
                        f"- {issue['name']}: "
                        f"{issue['message']}"
                    )


    # =====================================================
    # QUALITY GATE RESULT
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "PROCESSING QUALITY GATE"
    )

    print(
        "========================================"
    )


    print(
        f"\nRequired PASS rate: "
        f"{args.required_pass_rate:.2%}"
    )

    print(
        f"Observed PASS rate: "
        f"{pass_rate:.2%}"
    )

    print(
        f"\nQUALITY GATE: "
        f"{quality_gate}"
    )


    if quality_gate == "PASS":

        print(
            "\nThe parser/normalizer pipeline "
            "has passed the current project "
            "quality threshold."
        )

        print(
            "Review any WARNING documents "
            "before large-scale chunking."
        )


    else:

        print(
            "\nDo not mass-chunk the corpus yet."
        )

        print(
            "Review systemic parser/normalizer "
            "issues and rerun this validation."
        )


    # =====================================================
    # SAVE LOCAL JSON REPORT
    # =====================================================

    report = {
        "configuration": {
            "sample_size": sample_size,
            "seed": args.seed,
            "required_pass_rate": (
                args.required_pass_rate
            ),
            "raw_bucket": raw_bucket,
        },

        "summary": {
            "corpus_size": corpus_size,
            "attempted": attempted,
            "pass": passed,
            "warning": warnings,
            "fail": failed,
            "exceptions": (
                exception_count
            ),
            "pass_rate": round(
                pass_rate,
                6,
            ),
            "warning_rate": round(
                warning_rate,
                6,
            ),
            "failure_rate": round(
                failure_rate,
                6,
            ),
            "quality_gate": (
                quality_gate
            ),
            "elapsed_seconds": round(
                batch_elapsed,
                4,
            ),
        },

        "average_metrics": {
            "parsed_characters": round(
                safe_average(
                    parsed_character_values
                ),
                2,
            ),
            "normalized_characters": round(
                safe_average(
                    normalized_character_values
                ),
                2,
            ),
            "parsed_blocks": round(
                safe_average(
                    parsed_block_values
                ),
                2,
            ),
            "normalized_blocks": round(
                safe_average(
                    normalized_block_values
                ),
                2,
            ),
            "sections": round(
                safe_average(
                    section_values
                ),
                2,
            ),
            "headings": round(
                safe_average(
                    heading_values
                ),
                2,
            ),
            "tables": round(
                safe_average(
                    table_values
                ),
                2,
            ),
            "text_retention_ratio": round(
                safe_average(
                    text_retention_values
                ),
                6,
            ),
        },

        "form_statistics": dict(
            form_statistics
        ),

        "documents": results,
    }


    report_path = Path(
        args.report_path
    )


    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with report_path.open(
        "w",
        encoding="utf-8",
    ) as report_file:

        json.dump(
            report,
            report_file,
            indent=2,
            ensure_ascii=False,
        )


    print(
        "\n========================================"
    )

    print(
        "REPORT SAVED"
    )

    print(
        "========================================"
    )


    print(
        f"\n{report_path}"
    )


    print(
        f"\nTotal batch time: "
        f"{batch_elapsed:.2f} seconds"
    )


# =========================================================
# SCRIPT ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()