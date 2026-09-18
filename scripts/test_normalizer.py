import os

from dotenv import load_dotenv

from src.processing.normalizer import normalize_document
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
# CONNECT TO RAW GCS BUCKET
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
        "No SEC filings were found "
        "in the RAW bucket."
    )


# =========================================================
# SELECT ONE FILING
# =========================================================

filing_path = filing_objects[0]


print(
    "\n========================================"
)

print(
    "SEC NORMALIZER SMOKE TEST"
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
# PARSE RAW SEC FILING
# =========================================================

print(
    "\nParsing filing..."
)


parsed_document = parse_sec_filing(
    content
)


print(
    "Parsing complete."
)


# =========================================================
# NORMALIZE PARSED DOCUMENT
# =========================================================

print(
    "\nNormalizing document..."
)


normalized_document = normalize_document(
    parsed_document
)


print(
    "Normalization complete."
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
    parsed_document[
        "statistics"
    ].items()
):

    print(
        f"{key}: {value}"
    )


# =========================================================
# NORMALIZER STATISTICS
# =========================================================

print(
    "\n========================================"
)

print(
    "NORMALIZER STATISTICS"
)

print(
    "========================================"
)


for key, value in (
    normalized_document[
        "statistics"
    ].items()
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
    "NORMALIZED DOCUMENT TITLE"
)

print(
    "========================================"
)


title = normalized_document[
    "title"
]


if title:

    print(
        title
    )

else:

    print(
        "[No normalized title found]"
    )


# =========================================================
# DETECTED SECTIONS
# =========================================================

print(
    "\n========================================"
)

print(
    "DETECTED SECTIONS"
)

print(
    "========================================"
)


sections = normalized_document[
    "sections"
]


if not sections:

    print(
        "\n[No sections detected]"
    )


else:

    for index, section in enumerate(
        sections,
        start=1,
    ):

        print(
            f"{index}. {section}"
        )


# =========================================================
# FIRST 20 NORMALIZED BLOCKS
# =========================================================

print(
    "\n========================================"
)

print(
    "FIRST 20 NORMALIZED BLOCKS"
)

print(
    "========================================"
)


blocks = normalized_document[
    "blocks"
]


if not blocks:

    print(
        "\n[No normalized blocks produced]"
    )


else:

    for block in blocks[:20]:

        print(
            f"\nBLOCK INDEX: "
            f"{block['block_index']}"
        )

        print(
            f"TYPE: "
            f"{block['type']}"
        )

        print(
            f"SECTION: "
            f"{block['section']}"
        )

        print(
            f"CHARACTERS: "
            f"{block['character_count']}"
        )

        print(
            "TEXT:"
        )

        print(
            block["text"][:500]
        )


# =========================================================
# SHOW FIRST BLOCKS AFTER A REAL HEADING
# =========================================================

print(
    "\n========================================"
)

print(
    "SECTION CONTEXT CHECK"
)

print(
    "========================================"
)


heading_indexes = [
    index
    for index, block in enumerate(
        blocks
    )
    if block["type"] == "heading"
]


if not heading_indexes:

    print(
        "\nNo heading blocks were found."
    )


else:

    first_heading_position = (
        heading_indexes[0]
    )


    start = first_heading_position

    end = min(
        first_heading_position + 8,
        len(blocks),
    )


    print(
        "\nShowing the first heading "
        "and the blocks that follow it:"
    )


    for block in blocks[
        start:end
    ]:

        print(
            "\n----------------------------------------"
        )

        print(
            f"BLOCK INDEX: "
            f"{block['block_index']}"
        )

        print(
            f"TYPE: "
            f"{block['type']}"
        )

        print(
            f"SECTION: "
            f"{block['section']}"
        )

        print(
            "TEXT:"
        )

        print(
            block["text"][:500]
        )


# =========================================================
# BASIC QUALITY CHECK
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


normalized_blocks = (
    normalized_document[
        "statistics"
    ][
        "normalized_blocks"
    ]
)


section_count = (
    normalized_document[
        "statistics"
    ][
        "sections"
    ]
)


normalized_characters = (
    normalized_document[
        "statistics"
    ][
        "normalized_characters"
    ]
)


print(
    f"\nNormalized blocks: "
    f"{normalized_blocks:,}"
)

print(
    f"Detected sections: "
    f"{section_count:,}"
)

print(
    f"Normalized characters: "
    f"{normalized_characters:,}"
)


if normalized_blocks == 0:

    print(
        "\nWARNING: "
        "Normalizer produced no blocks."
    )


elif section_count == 0:

    print(
        "\nWARNING: "
        "Normalizer produced blocks, "
        "but no sections were detected."
    )


else:

    print(
        "\nNormalizer successfully produced "
        "structured blocks with section context."
    )


# =========================================================
# END
# =========================================================

print(
    "\n========================================"
)

print(
    "NORMALIZER SMOKE TEST COMPLETE"
)

print(
    "========================================"
)