import argparse
import csv
import hashlib
import json
import os
import re
import time
import warnings

from collections import Counter, defaultdict
from pathlib import Path

from bs4 import (
    BeautifulSoup,
    Tag,
    XMLParsedAsHTMLWarning,
)
from dotenv import load_dotenv

from src.storage.gcs_storage import GCSStorage


# =========================================================
# SUPPRESS EXPECTED SEC XHTML / XML WARNING
# =========================================================

warnings.filterwarnings(
    "ignore",
    category=XMLParsedAsHTMLWarning,
)


# =========================================================
# SEC HEADING PATTERN
# =========================================================

SEC_HEADING_PATTERN = re.compile(
    r"^(?:"
    r"PART\s+[IVX]+"
    r"|"
    r"ITEM\s+\d+[A-Z]?"
    r"(?:\s*[.\-–—:]|\s)"
    r")",
    re.IGNORECASE,
)


# =========================================================
# TAGS USED FOR STRUCTURAL HEADING DISCOVERY
# =========================================================

HEADING_CANDIDATE_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "div",
    "span",
    "td",
    "th",
    "font",
    "b",
    "strong",
}


# =========================================================
# TAGS CURRENT PRODUCTION PARSER USES AS BLOCKS
# =========================================================

CURRENT_PARSER_BLOCK_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
}


# =========================================================
# COMMAND-LINE ARGUMENTS
# =========================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Profile the SEC RAW corpus and identify "
            "structural HTML families."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Maximum number of filings to profile. "
            "0 means profile the full corpus."
        ),
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help=(
            "Print progress every N documents. "
            "Default: 25"
        ),
    )

    parser.add_argument(
        "--json-report",
        default=(
            "reports/"
            "sec_corpus_profile.json"
        ),
    )

    parser.add_argument(
        "--csv-report",
        default=(
            "reports/"
            "sec_corpus_profile.csv"
        ),
    )

    return parser.parse_args()


# =========================================================
# TEXT CLEANING
# =========================================================

def clean_text(
    text: str,
) -> str:

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# =========================================================
# CHECK HEADING-LIKE TEXT
# =========================================================

def looks_like_sec_heading(
    element: Tag,
) -> bool:

    text = clean_text(
        element.get_text(
            " ",
            strip=True,
        )
    )


    if not text:

        return False


    if len(text) > 300:

        return False


    return bool(
        SEC_HEADING_PATTERN.match(
            text
        )
    )


# =========================================================
# REMOVE LARGE PARENT DUPLICATES
# =========================================================

def contains_direct_matching_child(
    element: Tag,
) -> bool:

    for child in element.find_all(
        recursive=False
    ):

        if not isinstance(
            child,
            Tag,
        ):

            continue


        if (
            child.name
            in HEADING_CANDIDATE_TAGS
            and
            looks_like_sec_heading(
                child
            )
        ):

            return True


    return False


# =========================================================
# FIND HEADING CANDIDATES
# =========================================================

def find_heading_candidates(
    soup: BeautifulSoup,
) -> list[Tag]:

    candidates = []


    for element in soup.find_all(
        list(
            HEADING_CANDIDATE_TAGS
        )
    ):

        if not isinstance(
            element,
            Tag,
        ):

            continue


        if not looks_like_sec_heading(
            element
        ):

            continue


        if contains_direct_matching_child(
            element
        ):

            continue


        candidates.append(
            element
        )


    return candidates


# =========================================================
# COUNT TABLE ANCESTORS
# =========================================================

def count_table_ancestors(
    element: Tag,
) -> int:

    count = 0

    parent = element.parent


    while isinstance(
        parent,
        Tag,
    ):

        if parent.name == "table":

            count += 1


        parent = parent.parent


    return count


# =========================================================
# CAN CURRENT PARSER REACH THIS HEADING?
# =========================================================

def current_parser_can_reach_heading(
    element: Tag,
) -> bool:
    """
    The current parser mainly extracts:

        h1-h6
        p
        li
        table

    But paragraphs inside tables are skipped.

    Therefore a heading is considered structurally
    reachable when it belongs to, or sits inside,
    one of the supported textual block tags and that
    block is not itself inside a table.
    """

    node = element


    while isinstance(
        node,
        Tag,
    ):

        if (
            node.name
            in CURRENT_PARSER_BLOCK_TAGS
        ):

            if node.find_parent(
                "table"
            ) is None:

                return True


            return False


        if node.name == "table":

            return False


        node = node.parent


    return False


# =========================================================
# SIZE BUCKET
# =========================================================

def get_size_bucket(
    raw_bytes: int,
) -> str:

    if raw_bytes < 750_000:

        return "small"


    if raw_bytes < 2_000_000:

        return "medium"


    if raw_bytes < 5_000_000:

        return "large"


    return "very_large"


# =========================================================
# GENERIC COUNT BUCKET
# =========================================================

def count_bucket(
    value: int,
) -> str:

    if value == 0:

        return "0"


    if value <= 10:

        return "1_10"


    if value <= 50:

        return "11_50"


    if value <= 250:

        return "51_250"


    return "251_plus"


# =========================================================
# RATIO BUCKET
# =========================================================

def ratio_bucket(
    value: float,
) -> str:

    if value == 0:

        return "0"


    if value <= 0.25:

        return "low"


    if value <= 0.75:

        return "medium"


    return "high"


# =========================================================
# SAFE RATIO
# =========================================================

def safe_ratio(
    numerator: float,
    denominator: float,
) -> float:

    if denominator == 0:

        return 0.0


    return (
        numerator
        /
        denominator
    )


# =========================================================
# DOMINANT VALUE
# =========================================================

def dominant_key(
    counter: Counter,
) -> str:

    if not counter:

        return "none"


    return counter.most_common(
        1
    )[0][0]


# =========================================================
# STRUCTURAL FAMILY
# =========================================================

def build_structural_signature(
    metrics: dict,
) -> str:
    """
    Create a coarse structural signature.

    The purpose is NOT to identify every unique HTML
    file.

    The purpose is to group documents with broadly
    similar HTML representation.
    """

    signature_parts = [
        (
            "heading_tag="
            f"{metrics['dominant_heading_tag']}"
        ),
        (
            "heading_reach="
            f"{ratio_bucket(metrics['heading_reachable_ratio'])}"
        ),
        (
            "heading_table="
            f"{ratio_bucket(metrics['heading_inside_table_ratio'])}"
        ),
        (
            "p="
            f"{count_bucket(metrics['p_count'])}"
        ),
        (
            "div="
            f"{count_bucket(metrics['div_count'])}"
        ),
        (
            "span="
            f"{count_bucket(metrics['span_count'])}"
        ),
        (
            "table="
            f"{count_bucket(metrics['table_count'])}"
        ),
        (
            "headings="
            f"{count_bucket(metrics['heading_candidate_count'])}"
        ),
    ]


    return "|".join(
        signature_parts
    )


# =========================================================
# STABLE FAMILY ID
# =========================================================

def create_family_id(
    signature: str,
) -> str:

    digest = hashlib.sha1(
        signature.encode(
            "utf-8"
        )
    ).hexdigest()[:10]


    return (
        f"SF_{digest}"
    )


# =========================================================
# PARSER-RISK CLASSIFICATION
# =========================================================

def classify_parser_risk(
    heading_count: int,
    reachable_ratio: float,
) -> str:

    if heading_count == 0:

        return "unknown_no_headings"


    if reachable_ratio < 0.25:

        return "high"


    if reachable_ratio < 0.75:

        return "medium"


    return "low"


# =========================================================
# PROFILE ONE DOCUMENT
# =========================================================

def profile_document(
    content: bytes,
) -> dict:

    soup = BeautifulSoup(
        content,
        "lxml",
    )


    # -----------------------------------------------------
    # Remove non-content elements
    # -----------------------------------------------------

    for element in soup.find_all(
        [
            "script",
            "style",
            "noscript",
        ]
    ):

        element.extract()


    # -----------------------------------------------------
    # Count all HTML tags in one pass
    # -----------------------------------------------------

    tag_counter = Counter(
        element.name
        for element in soup.find_all(
            True
        )
        if element.name
    )


    p_count = tag_counter.get(
        "p",
        0,
    )

    div_count = tag_counter.get(
        "div",
        0,
    )

    span_count = tag_counter.get(
        "span",
        0,
    )

    table_count = tag_counter.get(
        "table",
        0,
    )

    td_count = tag_counter.get(
        "td",
        0,
    )

    th_count = tag_counter.get(
        "th",
        0,
    )


    h_count = sum(
        tag_counter.get(
            f"h{level}",
            0,
        )
        for level in range(
            1,
            7,
        )
    )


    # -----------------------------------------------------
    # Heading discovery
    # -----------------------------------------------------

    heading_candidates = (
        find_heading_candidates(
            soup
        )
    )


    heading_tag_counter = Counter()

    inside_table_count = 0

    reachable_count = 0

    maximum_table_depth = 0


    for element in heading_candidates:

        heading_tag_counter[
            element.name
        ] += 1


        table_depth = (
            count_table_ancestors(
                element
            )
        )


        maximum_table_depth = max(
            maximum_table_depth,
            table_depth,
        )


        if table_depth > 0:

            inside_table_count += 1


        if current_parser_can_reach_heading(
            element
        ):

            reachable_count += 1


    heading_count = len(
        heading_candidates
    )


    inside_table_ratio = safe_ratio(
        inside_table_count,
        heading_count,
    )


    reachable_ratio = safe_ratio(
        reachable_count,
        heading_count,
    )


    # -----------------------------------------------------
    # Dominant general text-bearing tag
    # -----------------------------------------------------

    text_tag_counter = Counter(
        {
            "p": p_count,
            "div": div_count,
            "span": span_count,
        }
    )


    metrics = {
        "p_count": p_count,
        "div_count": div_count,
        "span_count": span_count,
        "table_count": table_count,
        "td_count": td_count,
        "th_count": th_count,
        "html_heading_tag_count": (
            h_count
        ),

        "heading_candidate_count": (
            heading_count
        ),

        "heading_inside_table_count": (
            inside_table_count
        ),

        "heading_inside_table_ratio": round(
            inside_table_ratio,
            4,
        ),

        "heading_reachable_count": (
            reachable_count
        ),

        "heading_reachable_ratio": round(
            reachable_ratio,
            4,
        ),

        "maximum_heading_table_depth": (
            maximum_table_depth
        ),

        "dominant_heading_tag": (
            dominant_key(
                heading_tag_counter
            )
        ),

        "dominant_text_tag": (
            dominant_key(
                text_tag_counter
            )
        ),
    }


    signature = (
        build_structural_signature(
            metrics
        )
    )


    metrics[
        "structural_signature"
    ] = signature


    metrics[
        "structural_family"
    ] = create_family_id(
        signature
    )


    metrics[
        "current_parser_risk"
    ] = classify_parser_risk(
        heading_count=(
            heading_count
        ),
        reachable_ratio=(
            reachable_ratio
        ),
    )


    return metrics


# =========================================================
# GET MANIFEST PATH
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
# EXTRACT YEAR
# =========================================================

def extract_year(
    manifest: dict,
) -> str:

    date_value = (
        manifest.get(
            "report_date"
        )
        or
        manifest.get(
            "filing_date"
        )
        or
        ""
    )


    if len(date_value) >= 4:

        return date_value[:4]


    return "unknown"


# =========================================================
# SAVE CSV
# =========================================================

def save_csv(
    rows: list[dict],
    output_path: str,
):

    path = Path(
        output_path
    )


    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    if not rows:

        return


    fieldnames = list(
        rows[0].keys()
    )


    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )


        writer.writeheader()


        writer.writerows(
            rows
        )


# =========================================================
# MAIN
# =========================================================

def main():

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


    storage = GCSStorage(
        project_id=project_id,
        bucket_name=raw_bucket,
    )


    print(
        "\n========================================"
    )

    print(
        "SEC CORPUS STRUCTURAL PROFILING"
    )

    print(
        "========================================"
    )


    # =====================================================
    # DISCOVER FILINGS
    # =====================================================

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


    total_discovered = len(
        filing_objects
    )


    if args.limit > 0:

        filing_objects = (
            filing_objects[
                :args.limit
            ]
        )


    selected_count = len(
        filing_objects
    )


    print(
        f"\nRAW corpus filings discovered: "
        f"{total_discovered:,}"
    )

    print(
        f"Filings selected for profiling: "
        f"{selected_count:,}"
    )


    # =====================================================
    # AGGREGATE CONTAINERS
    # =====================================================

    results = []

    errors = []


    form_counter = Counter()

    year_counter = Counter()

    size_counter = Counter()

    risk_counter = Counter()

    family_counter = Counter()


    unique_ciks = set()

    unique_company_names = set()


    start_time = (
        time.perf_counter()
    )


    # =====================================================
    # PROFILE CORPUS
    # =====================================================

    for index, filing_path in enumerate(
        filing_objects,
        start=1,
    ):

        try:

            manifest_path = (
                get_manifest_path(
                    filing_path
                )
            )


            manifest = (
                storage.download_json(
                    manifest_path
                )
            )


            content = (
                storage.download_bytes(
                    filing_path
                )
            )


            structural_metrics = (
                profile_document(
                    content
                )
            )


            cik = (
                manifest.get(
                    "cik"
                )
                or
                "unknown"
            )


            company = (
                manifest.get(
                    "company"
                )
                or
                "unknown"
            )


            form = (
                manifest.get(
                    "form"
                )
                or
                "unknown"
            )


            year = extract_year(
                manifest
            )


            raw_bytes = len(
                content
            )


            size_bucket = (
                get_size_bucket(
                    raw_bytes
                )
            )


            row = {
                "document_id": (
                    manifest.get(
                        "document_id"
                    )
                ),

                "cik": cik,

                "company": company,

                "form": form,

                "filing_date": (
                    manifest.get(
                        "filing_date"
                    )
                ),

                "report_date": (
                    manifest.get(
                        "report_date"
                    )
                ),

                "year": year,

                "filing_path": (
                    filing_path
                ),

                "raw_bytes": (
                    raw_bytes
                ),

                "size_bucket": (
                    size_bucket
                ),

                **structural_metrics,
            }


            results.append(
                row
            )


            # ---------------------------------------------
            # Aggregate counters
            # ---------------------------------------------

            unique_ciks.add(
                cik
            )


            unique_company_names.add(
                company
            )


            form_counter[
                form
            ] += 1


            year_counter[
                year
            ] += 1


            size_counter[
                size_bucket
            ] += 1


            risk_counter[
                structural_metrics[
                    "current_parser_risk"
                ]
            ] += 1


            family_counter[
                structural_metrics[
                    "structural_family"
                ]
            ] += 1


        except Exception as error:

            errors.append(
                {
                    "filing_path": (
                        filing_path
                    ),
                    "error_type": (
                        type(error).__name__
                    ),
                    "error_message": (
                        str(error)
                    ),
                }
            )


        # ---------------------------------------------
        # Concise progress output
        # ---------------------------------------------

        if (
            index
            % args.progress_every
            == 0
            or
            index == selected_count
        ):

            elapsed = (
                time.perf_counter()
                -
                start_time
            )


            print(
                f"Processed "
                f"{index:,}/"
                f"{selected_count:,} "
                f"documents "
                f"({elapsed:.1f}s)"
            )


    # =====================================================
    # GROUP FAMILY DETAILS
    # =====================================================

    family_documents = defaultdict(
        list
    )


    for row in results:

        family_documents[
            row[
                "structural_family"
            ]
        ].append(
            row
        )


    family_summaries = []


    for family_id, documents in (
        family_documents.items()
    ):

        family_ciks = {
            document[
                "cik"
            ]
            for document in documents
        }


        family_forms = Counter(
            document[
                "form"
            ]
            for document in documents
        )


        family_years = Counter(
            document[
                "year"
            ]
            for document in documents
        )


        example_paths = [
            document[
                "filing_path"
            ]
            for document in documents[:5]
        ]


        family_summaries.append(
            {
                "family_id": (
                    family_id
                ),

                "document_count": len(
                    documents
                ),

                "unique_ciks": len(
                    family_ciks
                ),

                "forms": dict(
                    family_forms
                ),

                "years": dict(
                    family_years
                ),

                "structural_signature": (
                    documents[0][
                        "structural_signature"
                    ]
                ),

                "parser_risk": (
                    documents[0][
                        "current_parser_risk"
                    ]
                ),

                "example_paths": (
                    example_paths
                ),
            }
        )


    family_summaries.sort(
        key=lambda item: (
            item[
                "document_count"
            ]
        ),
        reverse=True,
    )


    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    elapsed = (
        time.perf_counter()
        -
        start_time
    )


    summary = {
        "raw_corpus_discovered": (
            total_discovered
        ),

        "documents_profiled": len(
            results
        ),

        "documents_failed": len(
            errors
        ),

        "unique_ciks": len(
            unique_ciks
        ),

        "unique_company_names": len(
            unique_company_names
        ),

        "form_distribution": dict(
            form_counter
        ),

        "year_distribution": dict(
            sorted(
                year_counter.items()
            )
        ),

        "size_distribution": dict(
            size_counter
        ),

        "current_parser_risk_distribution": (
            dict(
                risk_counter
            )
        ),

        "structural_family_count": len(
            family_summaries
        ),

        "elapsed_seconds": round(
            elapsed,
            2,
        ),
    }


    # =====================================================
    # SAVE JSON
    # =====================================================

    json_path = Path(
        args.json_report
    )


    json_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    report = {
        "summary": (
            summary
        ),

        "structural_families": (
            family_summaries
        ),

        "documents": (
            results
        ),

        "errors": (
            errors
        ),
    }


    with json_path.open(
        "w",
        encoding="utf-8",
    ) as json_file:

        json.dump(
            report,
            json_file,
            indent=2,
            ensure_ascii=False,
        )


    # =====================================================
    # SAVE CSV
    # =====================================================

    save_csv(
        rows=results,
        output_path=(
            args.csv_report
        ),
    )


    # =====================================================
    # TERMINAL SUMMARY
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "CORPUS PROFILE SUMMARY"
    )

    print(
        "========================================"
    )


    print(
        f"\nDocuments profiled: "
        f"{len(results):,}"
    )

    print(
        f"Errors: "
        f"{len(errors):,}"
    )

    print(
        f"Unique CIKs: "
        f"{len(unique_ciks):,}"
    )

    print(
        f"Unique company names: "
        f"{len(unique_company_names):,}"
    )

    print(
        f"Structural families: "
        f"{len(family_summaries):,}"
    )


    print(
        "\nForms:"
    )


    for form, count in (
        form_counter.most_common()
    ):

        print(
            f"  {form}: "
            f"{count:,}"
        )


    print(
        "\nCurrent parser risk:"
    )


    for risk, count in (
        risk_counter.most_common()
    ):

        print(
            f"  {risk}: "
            f"{count:,}"
        )


    print(
        "\nLargest structural families:"
    )


    for family in (
        family_summaries[:15]
    ):

        print(
            "\n"
            f"{family['family_id']} "
            f"- "
            f"{family['document_count']} docs"
        )

        print(
            f"  CIKs: "
            f"{family['unique_ciks']}"
        )

        print(
            f"  Risk: "
            f"{family['parser_risk']}"
        )

        print(
            f"  Signature:"
        )

        print(
            f"  "
            f"{family['structural_signature']}"
        )


    print(
        "\n========================================"
    )

    print(
        "REPORT FILES"
    )

    print(
        "========================================"
    )


    print(
        f"\nJSON:"
        f"\n{json_path}"
    )

    print(
        f"\nCSV:"
        f"\n{args.csv_report}"
    )

    print(
        f"\nElapsed: "
        f"{elapsed:.2f} seconds"
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()