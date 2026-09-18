import os

from dotenv import load_dotenv

from src.processing.sec_parser import parse_sec_filing
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
# DISCOVER RAW SEC OBJECTS
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
        "No SEC filings found "
        "in the RAW bucket."
    )


# =========================================================
# SELECT FIRST FILING
# =========================================================

filing_path = filing_objects[0]


print(
    "\n========================================"
)

print(
    "SEC PARSER SMOKE TEST"
)

print(
    "========================================"
)


print(
    f"\nRAW filing path:"
    f"\n{filing_path}"
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
# PARSE FILING
# =========================================================

print(
    "\nParsing filing..."
)


parsed = parse_sec_filing(
    content
)


print(
    "Parsing complete."
)


# =========================================================
# PARSER STATISTICS
# =========================================================

print(
    "\n========================================"
)

print(
    "PARSER STATISTICS"
)

print(
    "========================================"
)


for key, value in (
    parsed["statistics"].items()
):

    print(
        f"{key}: {value}"
    )


# =========================================================
# DOCUMENT TITLE
# =========================================================

print(
    "\n========================================"
)

print(
    "DOCUMENT TITLE"
)

print(
    "========================================"
)


if parsed["title"]:

    print(
        parsed["title"]
    )

else:

    print(
        "[No document title found]"
    )


# =========================================================
# FULL TEXT PREVIEW
# =========================================================

print(
    "\n========================================"
)

print(
    "FULL TEXT PREVIEW"
)

print(
    "========================================\n"
)


full_text = parsed[
    "full_text"
]


if full_text:

    print(
        full_text[:2000]
    )

else:

    print(
        "[No visible text extracted]"
    )


# =========================================================
# STRUCTURED BLOCK PREVIEW
# =========================================================

print(
    "\n========================================"
)

print(
    "FIRST 20 STRUCTURED BLOCKS"
)

print(
    "========================================"
)


blocks = parsed[
    "blocks"
]


if not blocks:

    print(
        "\n[No structured blocks extracted]"
    )


else:

    for index, block in enumerate(
        blocks[:20],
        start=1,
    ):

        print(
            f"\n[{index}] "
            f"{block['type'].upper()}"
        )

        print(
            block["text"][:500]
        )


# =========================================================
# SIMPLE QUALITY CHECK
# =========================================================

print(
    "\n========================================"
)

print(
    "BASIC QUALITY CHECK"
)

print(
    "========================================"
)


statistics = parsed[
    "statistics"
]


raw_bytes = statistics[
    "raw_bytes"
]

visible_characters = statistics[
    "visible_characters"
]

block_count = statistics[
    "blocks"
]


print(
    f"\nRaw bytes: "
    f"{raw_bytes:,}"
)

print(
    f"Visible characters: "
    f"{visible_characters:,}"
)

print(
    f"Structured blocks: "
    f"{block_count:,}"
)


if visible_characters == 0:

    print(
        "\nWARNING: "
        "No visible text was extracted."
    )


elif block_count == 0:

    print(
        "\nWARNING: "
        "Visible text was extracted, "
        "but structured blocks were not."
    )


else:

    print(
        "\nParser successfully produced "
        "visible text and structured blocks."
    )


# =========================================================
# END
# =========================================================

print(
    "\n========================================"
)

print(
    "SMOKE TEST COMPLETE"
)

print(
    "========================================"
)