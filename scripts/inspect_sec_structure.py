import argparse
import os
import re

from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

from src.storage.gcs_storage import GCSStorage


# =========================================================
# SEC HEADING PATTERNS WE WANT TO INSPECT
# =========================================================

HEADING_PATTERN = re.compile(
    r"^(?:"
    r"PART\s+[IVX]+"
    r"|"
    r"ITEM\s+\d+[A-Z]?"
    r"(?:\s*[.\-–—:]|\s)"
    r")",
    re.IGNORECASE,
)


# =========================================================
# COMMAND-LINE ARGUMENTS
# =========================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Inspect raw SEC HTML structure around "
            "PART / ITEM headings."
        )
    )

    parser.add_argument(
        "--filing-path",
        required=True,
        help=(
            "Full object path of the SEC filing "
            "inside the RAW GCS bucket."
        ),
    )

    parser.add_argument(
        "--max-matches",
        type=int,
        default=20,
        help=(
            "Maximum number of heading-like HTML "
            "elements to display. Default: 20"
        ),
    )

    parser.add_argument(
        "--ancestor-depth",
        type=int,
        default=6,
        help=(
            "Number of parent HTML elements to display. "
            "Default: 6"
        ),
    )

    return parser.parse_args()


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(
    text: str,
) -> str:
    """
    Collapse whitespace so SEC text becomes easier
    to inspect in terminal output.
    """

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# =========================================================
# SHORTEN TEXT
# =========================================================

def shorten_text(
    text: str,
    limit: int = 250,
) -> str:

    text = clean_text(
        text
    )

    if len(text) <= limit:
        return text

    return (
        text[:limit]
        +
        "..."
    )


# =========================================================
# FORMAT ONE HTML ELEMENT
# =========================================================

def describe_element(
    element: Tag,
) -> str:
    """
    Return a short description such as:

        <td class="textBlock">
    """

    tag_name = element.name


    element_id = element.get(
        "id"
    )


    classes = element.get(
        "class",
        [],
    )


    description = (
        f"<{tag_name}"
    )


    if element_id:

        description += (
            f' id="{element_id}"'
        )


    if classes:

        class_text = " ".join(
            classes
        )

        description += (
            f' class="{class_text}"'
        )


    description += ">"


    return description


# =========================================================
# COUNT TABLE ANCESTORS
# =========================================================

def count_table_ancestors(
    element: Tag,
) -> int:
    """
    Count how many parent <table> elements surround
    this candidate heading.
    """

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
# BUILD ANCESTOR CHAIN
# =========================================================

def build_ancestor_chain(
    element: Tag,
    max_depth: int,
) -> list[str]:
    """
    Example result:

        <span>
        <td>
        <tr>
        <tbody>
        <table>
        <body>
    """

    ancestors = []

    parent = element.parent

    depth = 0


    while (
        isinstance(
            parent,
            Tag,
        )
        and
        depth < max_depth
    ):

        ancestors.append(
            describe_element(
                parent
            )
        )

        parent = parent.parent

        depth += 1


    return ancestors


# =========================================================
# CHECK WHETHER ELEMENT LOOKS LIKE SEC HEADING
# =========================================================

def looks_like_sec_heading(
    element: Tag,
) -> bool:
    """
    Identify short elements whose visible text begins
    with PART or ITEM.

    We intentionally use a broad rule here because this
    script is diagnostic rather than production parsing.
    """

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
        HEADING_PATTERN.match(
            text
        )
    )


# =========================================================
# DETERMINE WHETHER ELEMENT HAS HEADING-LIKE CHILD
# =========================================================

def contains_smaller_matching_child(
    element: Tag,
) -> bool:
    """
    Prevent printing the same heading repeatedly for:

        <table>
          <tr>
            <td>
              <span>ITEM 1...</span>

    If a smaller child element already matches the same
    heading rule, we prefer the child.
    """

    for child in element.find_all(
        recursive=False
    ):

        if not isinstance(
            child,
            Tag,
        ):

            continue


        if looks_like_sec_heading(
            child
        ):

            return True


    return False


# =========================================================
# FIND CANDIDATE SEC HEADINGS
# =========================================================

def find_heading_candidates(
    soup: BeautifulSoup,
) -> list[Tag]:
    """
    Search common text-bearing HTML tags.

    SEC filings are not guaranteed to use normal
    <h1>/<h2> heading tags.
    """

    candidate_tags = [
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
    ]


    matches = []


    for element in soup.find_all(
        candidate_tags
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


        # Prefer the smallest useful element instead
        # of printing every parent container.
        if contains_smaller_matching_child(
            element
        ):

            continue


        matches.append(
            element
        )


    return matches


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


    # =====================================================
    # CONNECT TO GCS
    # =====================================================

    storage = GCSStorage(
        project_id=project_id,
        bucket_name=raw_bucket,
    )


    # =====================================================
    # DOWNLOAD RAW SEC FILING
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "SEC HTML STRUCTURE INSPECTION"
    )

    print(
        "========================================"
    )


    print(
        f"\nFiling:"
        f"\n{args.filing_path}"
    )


    content = storage.download_bytes(
        args.filing_path
    )


    print(
        f"\nRaw bytes: "
        f"{len(content):,}"
    )


    # =====================================================
    # PARSE RAW HTML ONLY FOR DIAGNOSTICS
    # =====================================================

    soup = BeautifulSoup(
        content,
        "lxml",
    )


    # Remove things that cannot contain useful filing
    # section headings.
    for element in soup.find_all(
        [
            "script",
            "style",
            "noscript",
        ]
    ):

        element.extract()


    # =====================================================
    # FIND HEADING-LIKE HTML ELEMENTS
    # =====================================================

    matches = find_heading_candidates(
        soup
    )


    print(
        f"\nHeading-like elements found: "
        f"{len(matches):,}"
    )


    # =====================================================
    # INSPECT MATCHES
    # =====================================================

    if not matches:

        print(
            "\nNo PART / ITEM candidate elements "
            "were detected."
        )

        return


    displayed = matches[
        :args.max_matches
    ]


    for index, element in enumerate(
        displayed,
        start=1,
    ):

        text = shorten_text(
            element.get_text(
                " ",
                strip=True,
            )
        )


        table_ancestor_count = (
            count_table_ancestors(
                element
            )
        )


        ancestors = (
            build_ancestor_chain(
                element=element,
                max_depth=(
                    args.ancestor_depth
                ),
            )
        )


        print(
            "\n========================================"
        )

        print(
            f"MATCH {index}"
        )

        print(
            "========================================"
        )


        print(
            f"\nTEXT:"
            f"\n{text}"
        )


        print(
            f"\nELEMENT:"
            f"\n{describe_element(element)}"
        )


        print(
            f"\nTABLE ANCESTORS: "
            f"{table_ancestor_count}"
        )


        if table_ancestor_count > 0:

            print(
                "INSIDE TABLE: YES"
            )

        else:

            print(
                "INSIDE TABLE: NO"
            )


        print(
            "\nANCESTOR CHAIN:"
        )


        for depth, ancestor in enumerate(
            ancestors,
            start=1,
        ):

            print(
                f"  {depth}. "
                f"{ancestor}"
            )


        # =================================================
        # DIRECT PARENT TEXT
        # =================================================

        parent = element.parent


        if isinstance(
            parent,
            Tag,
        ):

            parent_text = shorten_text(
                parent.get_text(
                    " ",
                    strip=True,
                ),
                limit=400,
            )


            print(
                "\nDIRECT PARENT TEXT:"
            )

            print(
                parent_text
            )


    # =====================================================
    # SUMMARY
    # =====================================================

    inside_table = sum(
        1
        for element in matches
        if count_table_ancestors(
            element
        ) > 0
    )


    outside_table = (
        len(matches)
        -
        inside_table
    )


    print(
        "\n\n========================================"
    )

    print(
        "STRUCTURE SUMMARY"
    )

    print(
        "========================================"
    )


    print(
        f"\nHeading-like elements: "
        f"{len(matches):,}"
    )

    print(
        f"Inside one or more tables: "
        f"{inside_table:,}"
    )

    print(
        f"Outside tables: "
        f"{outside_table:,}"
    )


    if matches:

        inside_ratio = (
            inside_table
            /
            len(matches)
        )


        print(
            f"Headings inside tables: "
            f"{inside_ratio:.2%}"
        )


    print(
        "\n========================================"
    )

    print(
        "INSPECTION COMPLETE"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()