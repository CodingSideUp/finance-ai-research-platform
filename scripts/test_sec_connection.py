import os

from dotenv import load_dotenv

from src.ingestion.sec_client import SECClient
from src.ingestion.filing_service import extract_filings
from src.ingestion.manifest import create_manifest
from src.storage.gcs_storage import GCSStorage


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------
# Read configuration
# ---------------------------------------------------------

user_agent = os.getenv("SEC_USER_AGENT")
gcp_project_id = os.getenv("GCP_PROJECT_ID")
gcs_raw_bucket = os.getenv("GCS_RAW_BUCKET")


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


# ---------------------------------------------------------
# Create SEC client
# ---------------------------------------------------------

client = SECClient(
    user_agent=user_agent
)


# ---------------------------------------------------------
# Apple CIK
# ---------------------------------------------------------

apple_cik = "320193"


# ---------------------------------------------------------
# Get Apple filing metadata from SEC
# ---------------------------------------------------------

data = client.get_company_submissions(
    cik=apple_cik
)


print("\nCompany:")
print(data["name"])


# ---------------------------------------------------------
# Extract latest 10-K / 10-Q filings
# ---------------------------------------------------------

filings = extract_filings(
    submissions=data,
    allowed_forms=("10-K", "10-Q"),
    limit=10,
)


print("\nSelected filings:\n")

for filing in filings:
    print(filing)


# ---------------------------------------------------------
# Select ONE filing for our first cloud upload test
# ---------------------------------------------------------

first_filing = filings[0]


# ---------------------------------------------------------
# Build the actual SEC archive URL
# ---------------------------------------------------------

filing_url = client.build_filing_url(
    cik=data["cik"],
    accession_number=first_filing["accession_number"],
    primary_document=first_filing["primary_document"],
)


print("\nFiling URL:")
print(filing_url)


# ---------------------------------------------------------
# Download the original filing as bytes
# ---------------------------------------------------------

filing_content = client.download_filing(
    url=filing_url
)


print("\nDownloaded filing size:")
print(len(filing_content))


print("\nFirst 300 characters:")

print(
    filing_content[:300].decode(
        "utf-8",
        errors="replace",
    )
)


# ---------------------------------------------------------
# Create metadata manifest
# ---------------------------------------------------------

manifest = create_manifest(
    company=data["name"],
    cik=data["cik"],
    filing=first_filing,
    source_url=filing_url,
    content=filing_content,
)


print("\nManifest:\n")

for key, value in manifest.items():
    print(f"{key}: {value}")


# ---------------------------------------------------------
# Connect to Google Cloud Storage RAW bucket
# ---------------------------------------------------------

gcs = GCSStorage(
    project_id=gcp_project_id,
    bucket_name=gcs_raw_bucket,
)


# ---------------------------------------------------------
# Define the GCS location for this filing
# ---------------------------------------------------------

base_path = (
    f"sec/"
    f"{data['cik']}/"
    f"{first_filing['accession_number']}"
)


# ---------------------------------------------------------
# Upload original SEC filing
# ---------------------------------------------------------

gcs.upload_bytes(
    content=filing_content,
    destination_path=(
        f"{base_path}/"
        f"{first_filing['primary_document']}"
    ),
    content_type="text/html",
)


# ---------------------------------------------------------
# Upload metadata manifest
# ---------------------------------------------------------

gcs.upload_json(
    data=manifest,
    destination_path=(
        f"{base_path}/manifest.json"
    ),
)


# ---------------------------------------------------------
# Confirm successful upload
# ---------------------------------------------------------

print("\nGCS upload complete:")

print(
    f"gs://{gcs_raw_bucket}/"
    f"{base_path}/"
)


# ---------------------------------------------------------
# Close SEC HTTP client
# ---------------------------------------------------------

client.close()