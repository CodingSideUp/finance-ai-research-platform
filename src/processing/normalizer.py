import re
import unicodedata


# =========================================================
# NORMALIZE GENERAL TEXT
# =========================================================

def _normalize_text(
    text: str,
) -> str:
    """
    Normalize general filing text.

    The goal is consistency, not aggressive cleaning.

    We preserve:
    - words
    - numbers
    - financial symbols
    - punctuation
    - meaningful sentence structure
    """

    if not text:
        return ""

    # -----------------------------------------------------
    # Normalize Unicode representations
    #
    # Example:
    # unusual compatibility characters
    # become consistent Unicode equivalents.
    # -----------------------------------------------------

    text = unicodedata.normalize(
        "NFKC",
        text,
    )


    # -----------------------------------------------------
    # Replace non-breaking spaces
    # -----------------------------------------------------

    text = text.replace(
        "\xa0",
        " ",
    )


    # -----------------------------------------------------
    # Normalize repeated horizontal whitespace
    # -----------------------------------------------------

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )


    # -----------------------------------------------------
    # Normalize excessive blank lines
    # -----------------------------------------------------

    text = re.sub(
        r"\n[ \t]*\n+",
        "\n",
        text,
    )


    # -----------------------------------------------------
    # Remove whitespace before punctuation
    #
    # Example:
    #
    # "AAR CORP ."
    #
    # becomes:
    #
    # "AAR CORP."
    # -----------------------------------------------------

    text = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        text,
    )


    return text.strip()


# =========================================================
# NORMALIZE TABLE TEXT
# =========================================================

def _normalize_table_text(
    text: str,
) -> str:
    """
    Normalize table text while preserving row structure
    and the pipe separators produced by sec_parser.py.
    """

    if not text:
        return ""

    normalized_rows = []


    for row in text.splitlines():

        row = unicodedata.normalize(
            "NFKC",
            row,
        )

        row = row.replace(
            "\xa0",
            " ",
        )

        row = re.sub(
            r"[ \t]+",
            " ",
            row,
        )


        # ---------------------------------------------
        # Standardize spacing around table separators
        # ---------------------------------------------

        cells = [
            cell.strip()
            for cell in row.split("|")
        ]


        cells = [
            cell
            for cell in cells
            if cell
        ]


        if cells:

            normalized_rows.append(
                " | ".join(
                    cells
                )
            )


    return "\n".join(
        normalized_rows
    ).strip()


# =========================================================
# NORMALIZE BLOCK
# =========================================================

def _normalize_block(
    block: dict,
) -> dict | None:
    """
    Normalize one structured block produced by
    sec_parser.py.

    Expected input:

        {
            "type": "paragraph",
            "text": "..."
        }
    """

    block_type = block.get(
        "type",
        "paragraph",
    )

    text = block.get(
        "text",
        "",
    )


    if block_type == "table":

        normalized_text = (
            _normalize_table_text(
                text
            )
        )

    else:

        normalized_text = (
            _normalize_text(
                text
            )
        )


    # -----------------------------------------------------
    # Ignore blocks that become empty after normalization
    # -----------------------------------------------------

    if not normalized_text:
        return None


    return {
        "type": block_type,
        "text": normalized_text,
    }


# =========================================================
# MAIN DOCUMENT NORMALIZER
# =========================================================

def normalize_document(
    parsed_document: dict,
) -> dict:
    """
    Normalize a document produced by parse_sec_filing().

    Responsibilities:

    1. normalize title
    2. normalize full text
    3. normalize every structured block
    4. remove immediate duplicate blocks
    5. assign section context
    6. assign stable block indexes
    7. calculate normalization statistics

    This function does NOT perform chunking.
    """


    # =====================================================
    # 1. NORMALIZE DOCUMENT TITLE
    # =====================================================

    title = _normalize_text(
        parsed_document.get(
            "title",
            "",
        )
    )


    # =====================================================
    # 2. NORMALIZE FULL DOCUMENT TEXT
    # =====================================================

    full_text = _normalize_text(
        parsed_document.get(
            "full_text",
            "",
        )
    )


    # =====================================================
    # 3. NORMALIZE STRUCTURED BLOCKS
    # =====================================================

    original_blocks = (
        parsed_document.get(
            "blocks",
            []
        )
    )


    normalized_blocks = []


    # -----------------------------------------------------
    # Default section before first detected SEC heading
    # -----------------------------------------------------

    current_section = (
        "Document Start"
    )


    # -----------------------------------------------------
    # Used to remove immediate duplicates
    # -----------------------------------------------------

    previous_signature = None


    for block in original_blocks:

        normalized_block = (
            _normalize_block(
                block
            )
        )


        if normalized_block is None:
            continue


        block_type = (
            normalized_block[
                "type"
            ]
        )

        block_text = (
            normalized_block[
                "text"
            ]
        )


        # -------------------------------------------------
        # Deduplicate repeated neighboring blocks
        #
        # Signature includes both block type and text.
        # -------------------------------------------------

        signature = (
            block_type,
            block_text,
        )


        if signature == previous_signature:
            continue


        # -------------------------------------------------
        # Heading changes the current document section
        # -------------------------------------------------

        if block_type == "heading":

            current_section = (
                block_text
            )


        # -------------------------------------------------
        # Store normalized block with context
        # -------------------------------------------------

        normalized_blocks.append(
            {
                "block_index": len(
                    normalized_blocks
                ),
                "type": block_type,
                "section": current_section,
                "text": block_text,
                "character_count": len(
                    block_text
                ),
            }
        )


        previous_signature = signature


    # =====================================================
    # 4. CALCULATE STATISTICS
    # =====================================================

    heading_count = sum(
        1
        for block in normalized_blocks
        if block["type"] == "heading"
    )


    paragraph_count = sum(
        1
        for block in normalized_blocks
        if block["type"] == "paragraph"
    )


    table_count = sum(
        1
        for block in normalized_blocks
        if block["type"] == "table"
    )


    list_item_count = sum(
        1
        for block in normalized_blocks
        if block["type"] == "list_item"
    )


    section_names = []


    for block in normalized_blocks:

        section = block[
            "section"
        ]


        if (
            section not in section_names
        ):

            section_names.append(
                section
            )


    statistics = {
        "original_blocks": len(
            original_blocks
        ),
        "normalized_blocks": len(
            normalized_blocks
        ),
        "headings": heading_count,
        "paragraphs": paragraph_count,
        "tables": table_count,
        "list_items": list_item_count,
        "sections": len(
            section_names
        ),
        "normalized_characters": len(
            full_text
        ),
    }


    # =====================================================
    # 5. RETURN NORMALIZED DOCUMENT
    # =====================================================

    return {
        "title": title,
        "full_text": full_text,
        "blocks": normalized_blocks,
        "sections": section_names,
        "statistics": statistics,
    }