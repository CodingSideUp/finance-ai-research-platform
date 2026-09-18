import os

from dotenv import load_dotenv

from src.storage.gcs_storage import GCSStorage


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------
# Read configuration
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Connect to RAW bucket
# ---------------------------------------------------------

storage = GCSStorage(
    project_id=project_id,
    bucket_name=raw_bucket,
)


# ---------------------------------------------------------
# Find objects under SEC prefix
# ---------------------------------------------------------

objects = storage.list_objects(
    prefix="sec/"
)


print("\nTotal RAW objects found:")
print(len(objects))


# ---------------------------------------------------------
# Separate filings and manifests
# ---------------------------------------------------------

filing_objects = [
    path
    for path in objects
    if not path.endswith(
        "manifest.json"
    )
]


manifest_objects = [
    path
    for path in objects
    if path.endswith(
        "manifest.json"
    )
]


print("\nFiling objects:")
print(len(filing_objects))


print("\nManifest objects:")
print(len(manifest_objects))


# ---------------------------------------------------------
# Select one filing
# ---------------------------------------------------------

first_filing_path = (
    filing_objects[0]
)


print("\nFirst filing path:")
print(first_filing_path)


# ---------------------------------------------------------
# Download filing bytes
# ---------------------------------------------------------

filing_content = (
    storage.download_bytes(
        first_filing_path
    )
)


print("\nDownloaded filing bytes:")
print(len(filing_content))


print("\nFirst 300 characters:")

print(
    filing_content[:300].decode(
        "utf-8",
        errors="replace",
    )
)


# ---------------------------------------------------------
# Locate corresponding manifest
# ---------------------------------------------------------

base_path = (
    first_filing_path.rsplit(
        "/",
        1,
    )[0]
)


manifest_path = (
    f"{base_path}/manifest.json"
)


print("\nManifest path:")
print(manifest_path)


# ---------------------------------------------------------
# Download manifest
# ---------------------------------------------------------

manifest = (
    storage.download_json(
        manifest_path
    )
)


print("\nManifest:\n")

for key, value in manifest.items():
    print(
        f"{key}: {value}"
    )