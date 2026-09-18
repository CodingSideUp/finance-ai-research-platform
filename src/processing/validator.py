# =========================================================
# PROCESSING VALIDATION THRESHOLDS
# =========================================================

MIN_VISIBLE_CHARACTERS = 1000

MIN_NORMALIZED_CHARACTERS = 1000

MIN_NORMALIZED_BLOCKS = 10

WARNING_MIN_SECTIONS = 2

WARNING_TEXT_RETENTION_RATIO = 0.85

FAIL_TEXT_RETENTION_RATIO = 0.50

WARNING_BLOCK_RETENTION_RATIO = 0.80


# =========================================================
# REQUIRED MANIFEST FIELDS
# =========================================================

REQUIRED_MANIFEST_FIELDS = [
    "document_id",
    "company",
    "cik",
    "form",
    "accession_number",
    "source_url",
]


# =========================================================
# REQUIRED NORMALIZED BLOCK FIELDS
# =========================================================

REQUIRED_BLOCK_FIELDS = [
    "block_index",
    "type",
    "section",
    "text",
    "character_count",
]


# =========================================================
# CREATE VALIDATION CHECK
# =========================================================

def _create_check(
    name: str,
    status: str,
    message: str,
    value=None,
) -> dict:
    """
    Create one standardized validation result.

    Status must be:

        PASS
        WARNING
        FAIL
    """

    return {
        "name": name,
        "status": status,
        "message": message,
        "value": value,
    }


# =========================================================
# VALIDATE MANIFEST
# =========================================================

def _validate_manifest(
    manifest: dict,
) -> list[dict]:
    """
    Validate source-lineage metadata.

    Missing critical lineage fields are considered
    failures because downstream chunks must always
    be traceable to their original SEC filing.
    """

    checks = []

    missing_fields = [
        field
        for field in REQUIRED_MANIFEST_FIELDS
        if not manifest.get(field)
    ]


    if missing_fields:

        checks.append(
            _create_check(
                name="manifest_required_fields",
                status="FAIL",
                message=(
                    "Manifest is missing required "
                    "lineage fields."
                ),
                value=missing_fields,
            )
        )

    else:

        checks.append(
            _create_check(
                name="manifest_required_fields",
                status="PASS",
                message=(
                    "All required manifest fields "
                    "are present."
                ),
                value=len(
                    REQUIRED_MANIFEST_FIELDS
                ),
            )
        )


    return checks


# =========================================================
# VALIDATE PARSED DOCUMENT
# =========================================================

def _validate_parsed_document(
    parsed_document: dict,
) -> list[dict]:
    """
    Validate the output produced by sec_parser.py.
    """

    checks = []


    # -----------------------------------------------------
    # VISIBLE TEXT
    # -----------------------------------------------------

    full_text = parsed_document.get(
        "full_text",
        "",
    )

    visible_characters = len(
        full_text
    )


    if visible_characters == 0:

        checks.append(
            _create_check(
                name="parsed_visible_text",
                status="FAIL",
                message=(
                    "Parser extracted no visible text."
                ),
                value=visible_characters,
            )
        )


    elif (
        visible_characters
        <
        MIN_VISIBLE_CHARACTERS
    ):

        checks.append(
            _create_check(
                name="parsed_visible_text",
                status="FAIL",
                message=(
                    "Parsed document contains "
                    "suspiciously little visible text."
                ),
                value=visible_characters,
            )
        )


    else:

        checks.append(
            _create_check(
                name="parsed_visible_text",
                status="PASS",
                message=(
                    "Parser extracted sufficient "
                    "visible text."
                ),
                value=visible_characters,
            )
        )


    # -----------------------------------------------------
    # PARSED BLOCKS
    # -----------------------------------------------------

    blocks = parsed_document.get(
        "blocks",
        [],
    )


    if not blocks:

        checks.append(
            _create_check(
                name="parsed_blocks",
                status="FAIL",
                message=(
                    "Parser produced no structured "
                    "document blocks."
                ),
                value=0,
            )
        )


    else:

        checks.append(
            _create_check(
                name="parsed_blocks",
                status="PASS",
                message=(
                    "Parser produced structured blocks."
                ),
                value=len(
                    blocks
                ),
            )
        )


    return checks


# =========================================================
# VALIDATE NORMALIZED BLOCK SCHEMA
# =========================================================

def _validate_block_schema(
    blocks: list[dict],
) -> list[dict]:
    """
    Validate the structure of normalized blocks.

    Every downstream component should be able to
    rely on the same block contract.
    """

    malformed_blocks = []


    for position, block in enumerate(
        blocks
    ):

        missing_fields = [
            field
            for field in REQUIRED_BLOCK_FIELDS
            if field not in block
        ]


        if missing_fields:

            malformed_blocks.append(
                {
                    "position": position,
                    "missing_fields": (
                        missing_fields
                    ),
                }
            )


    if malformed_blocks:

        return [
            _create_check(
                name="normalized_block_schema",
                status="FAIL",
                message=(
                    "One or more normalized blocks "
                    "do not satisfy the expected "
                    "data contract."
                ),
                value=malformed_blocks[:10],
            )
        ]


    return [
        _create_check(
            name="normalized_block_schema",
            status="PASS",
            message=(
                "All normalized blocks satisfy "
                "the expected data contract."
            ),
            value=len(
                blocks
            ),
        )
    ]


# =========================================================
# VALIDATE NORMALIZED DOCUMENT
# =========================================================

def _validate_normalized_document(
    parsed_document: dict,
    normalized_document: dict,
) -> list[dict]:
    """
    Validate output from normalizer.py.
    """

    checks = []


    # -----------------------------------------------------
    # NORMALIZED TEXT SIZE
    # -----------------------------------------------------

    normalized_text = (
        normalized_document.get(
            "full_text",
            "",
        )
    )


    normalized_characters = len(
        normalized_text
    )


    if normalized_characters == 0:

        checks.append(
            _create_check(
                name="normalized_visible_text",
                status="FAIL",
                message=(
                    "Normalizer produced no text."
                ),
                value=0,
            )
        )


    elif (
        normalized_characters
        <
        MIN_NORMALIZED_CHARACTERS
    ):

        checks.append(
            _create_check(
                name="normalized_visible_text",
                status="FAIL",
                message=(
                    "Normalized document contains "
                    "suspiciously little text."
                ),
                value=normalized_characters,
            )
        )


    else:

        checks.append(
            _create_check(
                name="normalized_visible_text",
                status="PASS",
                message=(
                    "Normalizer retained sufficient "
                    "document text."
                ),
                value=normalized_characters,
            )
        )


    # -----------------------------------------------------
    # NORMALIZED BLOCK COUNT
    # -----------------------------------------------------

    normalized_blocks = (
        normalized_document.get(
            "blocks",
            [],
        )
    )


    block_count = len(
        normalized_blocks
    )


    if block_count == 0:

        checks.append(
            _create_check(
                name="normalized_blocks",
                status="FAIL",
                message=(
                    "Normalizer produced no blocks."
                ),
                value=0,
            )
        )


    elif (
        block_count
        <
        MIN_NORMALIZED_BLOCKS
    ):

        checks.append(
            _create_check(
                name="normalized_blocks",
                status="FAIL",
                message=(
                    "Normalizer produced suspiciously "
                    "few document blocks."
                ),
                value=block_count,
            )
        )


    else:

        checks.append(
            _create_check(
                name="normalized_blocks",
                status="PASS",
                message=(
                    "Normalizer produced sufficient "
                    "structured blocks."
                ),
                value=block_count,
            )
        )


    # -----------------------------------------------------
    # SECTION DETECTION
    # -----------------------------------------------------

    sections = normalized_document.get(
        "sections",
        [],
    )


    section_count = len(
        sections
    )


    if section_count == 0:

        checks.append(
            _create_check(
                name="section_detection",
                status="WARNING",
                message=(
                    "No document sections were detected."
                ),
                value=0,
            )
        )


    elif (
        section_count
        <
        WARNING_MIN_SECTIONS
    ):

        checks.append(
            _create_check(
                name="section_detection",
                status="WARNING",
                message=(
                    "Very few document sections "
                    "were detected."
                ),
                value=section_count,
            )
        )


    else:

        checks.append(
            _create_check(
                name="section_detection",
                status="PASS",
                message=(
                    "Document contains usable "
                    "section structure."
                ),
                value=section_count,
            )
        )


    # -----------------------------------------------------
    # HEADING DETECTION
    # -----------------------------------------------------

    heading_count = (
        normalized_document
        .get(
            "statistics",
            {},
        )
        .get(
            "headings",
            0,
        )
    )


    if heading_count == 0:

        checks.append(
            _create_check(
                name="heading_detection",
                status="WARNING",
                message=(
                    "No SEC section headings "
                    "were detected."
                ),
                value=0,
            )
        )


    else:

        checks.append(
            _create_check(
                name="heading_detection",
                status="PASS",
                message=(
                    "SEC section headings were detected."
                ),
                value=heading_count,
            )
        )


    # -----------------------------------------------------
    # TEXT RETENTION RATIO
    # -----------------------------------------------------

    parsed_characters = len(
        parsed_document.get(
            "full_text",
            "",
        )
    )


    if parsed_characters > 0:

        text_retention_ratio = (
            normalized_characters
            /
            parsed_characters
        )


        if (
            text_retention_ratio
            <
            FAIL_TEXT_RETENTION_RATIO
        ):

            status = "FAIL"

            message = (
                "Normalization removed an "
                "unexpectedly large amount of text."
            )


        elif (
            text_retention_ratio
            <
            WARNING_TEXT_RETENTION_RATIO
        ):

            status = "WARNING"

            message = (
                "Normalization retained less text "
                "than expected."
            )


        else:

            status = "PASS"

            message = (
                "Normalization preserved the "
                "majority of parsed text."
            )


        checks.append(
            _create_check(
                name="text_retention_ratio",
                status=status,
                message=message,
                value=round(
                    text_retention_ratio,
                    4,
                ),
            )
        )


    # -----------------------------------------------------
    # BLOCK RETENTION RATIO
    # -----------------------------------------------------

    parsed_blocks = parsed_document.get(
        "blocks",
        [],
    )


    parsed_block_count = len(
        parsed_blocks
    )


    if parsed_block_count > 0:

        block_retention_ratio = (
            block_count
            /
            parsed_block_count
        )


        if (
            block_retention_ratio
            <
            WARNING_BLOCK_RETENTION_RATIO
        ):

            status = "WARNING"

            message = (
                "Normalization removed a relatively "
                "large number of parsed blocks."
            )


        else:

            status = "PASS"

            message = (
                "Normalization preserved the "
                "majority of parsed blocks."
            )


        checks.append(
            _create_check(
                name="block_retention_ratio",
                status=status,
                message=message,
                value=round(
                    block_retention_ratio,
                    4,
                ),
            )
        )


    # -----------------------------------------------------
    # BLOCK DATA CONTRACT
    # -----------------------------------------------------

    checks.extend(
        _validate_block_schema(
            normalized_blocks
        )
    )


    return checks


# =========================================================
# DETERMINE OVERALL STATUS
# =========================================================

def _determine_overall_status(
    checks: list[dict],
) -> str:
    """
    Overall document result:

    Any FAIL
        -> FAIL

    No FAIL but at least one WARNING
        -> WARNING

    Otherwise
        -> PASS
    """

    statuses = [
        check[
            "status"
        ]
        for check in checks
    ]


    if "FAIL" in statuses:

        return "FAIL"


    if "WARNING" in statuses:

        return "WARNING"


    return "PASS"


# =========================================================
# MAIN PROCESSING VALIDATOR
# =========================================================

def validate_processed_document(
    parsed_document: dict,
    normalized_document: dict,
    manifest: dict,
) -> dict:
    """
    Validate one SEC document after parsing and
    normalization.

    This function does NOT alter the document.

    It acts as a quality gate before chunking.

    Returns:

        {
            "document_id": ...,
            "status": "PASS/WARNING/FAIL",
            "checks": [...],
            "summary": {...},
            "metrics": {...}
        }
    """

    checks = []


    # =====================================================
    # 1. SOURCE / LINEAGE VALIDATION
    # =====================================================

    checks.extend(
        _validate_manifest(
            manifest
        )
    )


    # =====================================================
    # 2. PARSER OUTPUT VALIDATION
    # =====================================================

    checks.extend(
        _validate_parsed_document(
            parsed_document
        )
    )


    # =====================================================
    # 3. NORMALIZER OUTPUT VALIDATION
    # =====================================================

    checks.extend(
        _validate_normalized_document(
            parsed_document=parsed_document,
            normalized_document=(
                normalized_document
            ),
        )
    )


    # =====================================================
    # 4. DETERMINE DOCUMENT STATUS
    # =====================================================

    overall_status = (
        _determine_overall_status(
            checks
        )
    )


    # =====================================================
    # 5. SUMMARY COUNTS
    # =====================================================

    pass_count = sum(
        1
        for check in checks
        if check["status"] == "PASS"
    )


    warning_count = sum(
        1
        for check in checks
        if check["status"] == "WARNING"
    )


    fail_count = sum(
        1
        for check in checks
        if check["status"] == "FAIL"
    )


    # =====================================================
    # 6. USEFUL METRICS
    # =====================================================

    parsed_text = parsed_document.get(
        "full_text",
        "",
    )


    normalized_text = (
        normalized_document.get(
            "full_text",
            "",
        )
    )


    normalized_blocks = (
        normalized_document.get(
            "blocks",
            [],
        )
    )


    sections = normalized_document.get(
        "sections",
        [],
    )


    metrics = {
        "raw_bytes": (
            parsed_document
            .get(
                "statistics",
                {},
            )
            .get(
                "raw_bytes",
                0,
            )
        ),

        "parsed_characters": len(
            parsed_text
        ),

        "normalized_characters": len(
            normalized_text
        ),

        "parsed_blocks": len(
            parsed_document.get(
                "blocks",
                [],
            )
        ),

        "normalized_blocks": len(
            normalized_blocks
        ),

        "sections": len(
            sections
        ),

        "headings": (
            normalized_document
            .get(
                "statistics",
                {},
            )
            .get(
                "headings",
                0,
            )
        ),

        "tables": (
            normalized_document
            .get(
                "statistics",
                {},
            )
            .get(
                "tables",
                0,
            )
        ),
    }


    # =====================================================
    # 7. FINAL VALIDATION RESULT
    # =====================================================

    return {
        "document_id": manifest.get(
            "document_id"
        ),

        "company": manifest.get(
            "company"
        ),

        "form": manifest.get(
            "form"
        ),

        "status": overall_status,

        "checks": checks,

        "summary": {
            "passed_checks": pass_count,
            "warning_checks": warning_count,
            "failed_checks": fail_count,
        },

        "metrics": metrics,
    }