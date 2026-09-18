import argparse
import os
import time

from dotenv import load_dotenv

from src.ingestion.sec_client import SECClient
from src.ingestion.filing_service import extract_filings
from src.ingestion.manifest import create_manifest
from src.storage.gcs_storage import GCSStorage

#This is the orchestrator
#               ingest_sec.py

#        ┌────────────┼────────────┐
#        ▼            ▼            ▼
#  SECClient    filing_service   manifest

#                       │
#                       ▼
#                   GCSStorage
# =========================================================
# COMMAND-LINE ARGUMENTS
# =========================================================

def parse_arguments():
    """
    Read ingestion settings from the terminal.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Ingest SEC 10-K and 10-Q filings "
            "into Google Cloud Storage."
        )
    )

    parser.add_argument(
        "--target-documents",
        type=int,
        default=100,
        help=(
            "Target number of successfully available "
            "documents in the corpus."
        ),
    )

    parser.add_argument(
        "--filings-per-company",
        type=int,
        default=5,
        help=(
            "Maximum number of 10-K / 10-Q filings "
            "selected per company."
        ),
    )

    parser.add_argument(
        "--max-companies",
        type=int,
        default=500,
        help=(
            "Maximum number of companies to scan."
        ),
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.25,
        help=(
            "Delay in seconds between SEC requests."
        ),
    )

    return parser.parse_args()


# =========================================================
# COMPANY UNIVERSE
# =========================================================

def build_company_universe(
    ticker_data: dict,
) -> list[dict]:
    """
    Convert SEC company_tickers.json into a clean,
    deterministic list of unique companies.

    Duplicate CIKs are removed.
    """

    companies = []

    seen_ciks = set()

    for record in ticker_data.values():

        cik = str(
            record["cik_str"]
        ).zfill(10)

        if cik in seen_ciks:
            continue

        seen_ciks.add(
            cik
        )

        companies.append(
            {
                "cik": cik,
                "ticker": record["ticker"],
                "company": record["title"],
            }
        )

    companies.sort(
        key=lambda company: company["ticker"]
    )

    return companies


# =========================================================
# LOAD CONFIGURATION
# =========================================================

args = parse_arguments()

load_dotenv()


user_agent = os.getenv(
    "SEC_USER_AGENT"
)

gcp_project_id = os.getenv(
    "GCP_PROJECT_ID"
)

gcs_raw_bucket = os.getenv(
    "GCS_RAW_BUCKET"
)


if not user_agent:
    raise ValueError(
        "SEC_USER_AGENT is missing from .env"
    )

if not gcp_project_id:
    raise ValueError(
        "GCP_PROJECT_ID is missing from .env"
    )

if not gcs_raw_bucket:
    raise ValueError(
        "GCS_RAW_BUCKET is missing from .env"
    )


if args.target_documents <= 0:
    raise ValueError(
        "--target-documents must be greater than 0"
    )

if args.filings_per_company <= 0:
    raise ValueError(
        "--filings-per-company must be greater than 0"
    )

if args.max_companies <= 0:
    raise ValueError(
        "--max-companies must be greater than 0"
    )


# =========================================================
# CREATE CLIENTS
# =========================================================

sec_client = SECClient(
    user_agent=user_agent
)

gcs = GCSStorage(
    project_id=gcp_project_id,
    bucket_name=gcs_raw_bucket,
)


# =========================================================
# RUN METRICS
# =========================================================

companies_scanned = 0

companies_failed = 0

filings_discovered = 0

filings_ingested = 0

filings_skipped = 0

filings_failed = 0

bytes_downloaded = 0


run_start_time = time.time()


# =========================================================
# START INGESTION
# =========================================================

print("\n========================================")
print("SCALABLE SEC INGESTION STARTED")
print("========================================")

print(
    f"\nTarget documents: "
    f"{args.target_documents}"
)

print(
    f"Filings per company: "
    f"{args.filings_per_company}"
)

print(
    f"Maximum companies: "
    f"{args.max_companies}"
)

print(
    f"SEC request delay: "
    f"{args.request_delay} seconds"
)


try:

    # -----------------------------------------------------
    # Load SEC company universe
    # -----------------------------------------------------

    print(
        "\nDownloading SEC company universe..."
    )

    ticker_data = (
        sec_client.get_company_tickers()
    )

    time.sleep(
        args.request_delay
    )

    companies = build_company_universe(
        ticker_data
    )

    print(
        f"Unique companies available: "
        f"{len(companies)}"
    )


    # -----------------------------------------------------
    # Iterate through companies
    # -----------------------------------------------------

    for company in companies:

        completed_documents = (
            filings_ingested
            + filings_skipped
        )

        if (
            completed_documents
            >= args.target_documents
        ):
            break

        if (
            companies_scanned
            >= args.max_companies
        ):
            break


        companies_scanned += 1


        cik = company["cik"]

        ticker = company["ticker"]

        company_name = company["company"]


        print(
            "\n========================================"
        )

        print(
            f"Company "
            f"{companies_scanned}: "
            f"{ticker} | "
            f"{company_name}"
        )

        print(
            f"CIK: {cik}"
        )


        # -------------------------------------------------
        # Retrieve company submissions
        # -------------------------------------------------

        try:

            submissions = (
                sec_client.get_company_submissions(
                    cik=cik
                )
            )

            time.sleep(
                args.request_delay
            )

        except Exception as error:

            companies_failed += 1

            print(
                "COMPANY FAILED"
            )

            print(
                f"Reason: {error}"
            )

            continue


        # -------------------------------------------------
        # Select recent 10-K / 10-Q filings
        # -------------------------------------------------

        filings = extract_filings(
            submissions=submissions,
            allowed_forms=(
                "10-K",
                "10-Q",
            ),
            limit=args.filings_per_company,
        )


        filings_discovered += len(
            filings
        )


        if not filings:

            print(
                "No matching 10-K / 10-Q filings."
            )

            continue


        print(
            f"Selected filings: "
            f"{len(filings)}"
        )


        # -------------------------------------------------
        # Process each filing
        # -------------------------------------------------

        for filing in filings:

            completed_documents = (
                filings_ingested
                + filings_skipped
            )

            if (
                completed_documents
                >= args.target_documents
            ):
                break


            accession_number = (
                filing["accession_number"]
            )

            primary_document = (
                filing["primary_document"]
            )

            form = filing["form"]


            base_path = (
                f"sec/"
                f"{cik}/"
                f"{accession_number}"
            )

            manifest_destination = (
                f"{base_path}/"
                f"manifest.json"
            )


            # ---------------------------------------------
            # Idempotency check
            # ---------------------------------------------

            if gcs.object_exists(
                manifest_destination
            ):

                filings_skipped += 1

                print(
                    f"[SKIP] "
                    f"{form} | "
                    f"{accession_number}"
                )

                continue


            # ---------------------------------------------
            # New filing ingestion
            # ---------------------------------------------

            try:

                filing_url = (
                    sec_client.build_filing_url(
                        cik=cik,
                        accession_number=(
                            accession_number
                        ),
                        primary_document=(
                            primary_document
                        ),
                    )
                )


                print(
                    f"[DOWNLOAD] "
                    f"{form} | "
                    f"{accession_number}"
                )


                filing_content = (
                    sec_client.download_filing(
                        url=filing_url
                    )
                )


                time.sleep(
                    args.request_delay
                )


                bytes_downloaded += len(
                    filing_content
                )


                # -----------------------------------------
                # Create manifest
                # -----------------------------------------

                manifest = create_manifest(
                    company=submissions["name"],
                    cik=cik,
                    filing=filing,
                    source_url=filing_url,
                    content=filing_content,
                )


                # -----------------------------------------
                # Upload filing
                # -----------------------------------------

                filing_destination = (
                    f"{base_path}/"
                    f"{primary_document}"
                )


                gcs.upload_bytes(
                    content=filing_content,
                    destination_path=(
                        filing_destination
                    ),
                    content_type="text/html",
                )


                # -----------------------------------------
                # Upload manifest LAST
                #
                # Manifest acts as completion marker.
                # -----------------------------------------

                gcs.upload_json(
                    data=manifest,
                    destination_path=(
                        manifest_destination
                    ),
                )


                filings_ingested += 1


                print(
                    f"[SUCCESS] "
                    f"{accession_number} | "
                    f"{len(filing_content):,} bytes"
                )


            except Exception as error:

                filings_failed += 1


                print(
                    f"[FAILED] "
                    f"{accession_number}"
                )

                print(
                    f"Reason: {error}"
                )


finally:

    sec_client.close()


# =========================================================
# FINAL RUN SUMMARY
# =========================================================

elapsed_seconds = (
    time.time()
    - run_start_time
)


completed_documents = (
    filings_ingested
    + filings_skipped
)


print("\n========================================")
print("SCALABLE SEC INGESTION COMPLETE")
print("========================================")


print(
    f"\nCompanies scanned: "
    f"{companies_scanned}"
)

print(
    f"Companies failed: "
    f"{companies_failed}"
)

print(
    f"Filings discovered: "
    f"{filings_discovered}"
)

print(
    f"New filings ingested: "
    f"{filings_ingested}"
)

print(
    f"Existing filings skipped: "
    f"{filings_skipped}"
)

print(
    f"Filings failed: "
    f"{filings_failed}"
)

print(
    f"Completed corpus documents: "
    f"{completed_documents}"
)

print(
    f"Downloaded bytes this run: "
    f"{bytes_downloaded:,}"
)

print(
    f"Elapsed time: "
    f"{elapsed_seconds:.2f} seconds"
)

print(
    f"\nRAW bucket:"
    f"\ngs://{gcs_raw_bucket}/"
)


if (
    completed_documents
    < args.target_documents
):

    print(
        "\nWARNING:"
    )

    print(
        "The requested target was not reached. "
        "Increase --max-companies or inspect failures."
    )


# Why did we make it configurable?

# You ran:

# python -m scripts.ingest_sec \
#     --target-documents 1000 \
#     --filings-per-company 5 \
#     --max-companies 300

# Notice:

# 1000
# 5
# 300

# are parameters.

# The code itself didn't need rewriting.

# That's a major production principle.

# Bad:

# TARGET = 100

# Then manually edit source code every time.

# Better:

# --target-documents 1000

# Meaning:

# Configuration changes. Application logic does not.