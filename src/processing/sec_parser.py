import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from bs4.element import Tag


# =========================================================
# SUPPRESS EXPECTED SEC XHTML/XML WARNING
# =========================================================

warnings.filterwarnings(
    "ignore",
    category=XMLParsedAsHTMLWarning,
)


# =========================================================
# CONSTANTS
# =========================================================

TRUE_HEADING_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}


STANDARD_BLOCK_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "table",
}


# Modern and legacy SEC filings may represent headings
# using these tags instead of normal <p>/<h1> tags.
SUPPLEMENTAL_HEADING_TAGS = {
    "div",
    "span",
    "b",
    "strong",
    "font",
    "td",
    "th",
    "a",
    "p",
}


# We may promote a small heading element into a parent
# container when the parent provides the complete title.
#
# Example:
#
# <div>
#     <span>Item 1.</span>
#     <span>Financial Statements</span>
# </div>
#
# We prefer:
#
# Item 1. Financial Statements
#
# rather than only:
#
# Item 1.
PROMOTABLE_HEADING_CONTAINERS = {
    "span",
    "b",
    "strong",
    "font",
    "a",
    "div",
    "p",
    "td",
    "th",
}


# =========================================================
# LIGHT TEXT CLEANING
# =========================================================

def _clean_text(text: str) -> str:
    """
    Perform conservative whitespace cleanup.

    More advanced normalization happens later
    in normalizer.py.
    """

    if not text:
        return ""

    text = text.replace(
        "\xa0",
        " ",
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n",
        text,
    )

    return text.strip()


# =========================================================
# VALID TAG CHECK
# =========================================================

def _is_valid_tag(element) -> bool:
    """
    Check whether an object is a BeautifulSoup Tag.
    """

    return isinstance(
        element,
        Tag,
    )


# =========================================================
# HIDDEN ELEMENT DETECTION
# =========================================================

def _is_hidden(element: Tag) -> bool:
    """
    Detect HTML elements hidden using CSS
    or the HTML hidden attribute.
    """

    if not _is_valid_tag(
        element
    ):
        return False

    attrs = element.attrs or {}

    style_value = attrs.get(
        "style",
        "",
    )

    if not isinstance(
        style_value,
        str,
    ):
        style_value = str(
            style_value
        )

    normalized_style = (
        style_value
        .replace(
            " ",
            "",
        )
        .lower()
    )

    if "display:none" in normalized_style:
        return True

    if "visibility:hidden" in normalized_style:
        return True

    if "hidden" in attrs:
        return True

    return False


# =========================================================
# SEC SECTION HEADING DETECTION
# =========================================================

def _looks_like_sec_heading(
    text: str,
) -> bool:
    """
    Detect business-relevant SEC filing headings.

    We deliberately avoid treating every uppercase
    phrase as a heading.

    The main goal is to identify SEC structure such as:

        PART I
        PART II
        ITEM 1
        ITEM 1A
        ITEM 2
        Financial Statements
        Risk Factors
        MD&A
        Signatures
    """

    if not text:
        return False

    normalized = " ".join(
        text.split()
    ).strip()

    if not normalized:
        return False

    if len(normalized) > 250:
        return False

    upper_text = normalized.upper()


    # -----------------------------------------------------
    # PART sections
    # -----------------------------------------------------

    if re.match(
        r"^PART\s+[IVX]+(?:\.|\s|$|[-–—:])",
        upper_text,
    ):
        return True


    # -----------------------------------------------------
    # ITEM sections
    #
    # Examples:
    #
    # ITEM 1.
    # ITEM 1A.
    # ITEM 2
    # ITEM 7 – MANAGEMENT'S DISCUSSION...
    # ITEM 1 | FINANCIAL STATEMENTS
    # -----------------------------------------------------

    if re.match(
        r"^ITEM\s+\d+[A-Z]?\s*[.:]?(?:\s|\||[-–—]|$)",
        upper_text,
    ):
        return True


    # -----------------------------------------------------
    # Exact common SEC section titles
    # -----------------------------------------------------

    exact_headings = {
        "FINANCIAL STATEMENTS",
        "CONSOLIDATED FINANCIAL STATEMENTS",
        "CONDENSED CONSOLIDATED FINANCIAL STATEMENTS",
        "RISK FACTORS",
        "LEGAL PROCEEDINGS",
        "CONTROLS AND PROCEDURES",
        "OTHER INFORMATION",
        "SIGNATURES",
        "EXHIBITS",
        "CYBERSECURITY",
        "MINE SAFETY DISCLOSURES",
        "DEFAULTS UPON SENIOR SECURITIES",
    }


    if upper_text in exact_headings:
        return True


    # -----------------------------------------------------
    # Common section-title prefixes
    # -----------------------------------------------------

    heading_prefixes = (
        "MANAGEMENT'S DISCUSSION AND ANALYSIS",
        "MANAGEMENT’S DISCUSSION AND ANALYSIS",
        "QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK",
        "NOTES TO CONSOLIDATED FINANCIAL STATEMENTS",
        "NOTES TO CONDENSED CONSOLIDATED FINANCIAL STATEMENTS",
    )


    for prefix in heading_prefixes:

        if upper_text.startswith(
            prefix
        ):
            return True


    return False


# =========================================================
# COUNT SEC HEADING MARKERS
# =========================================================

def _count_heading_markers(
    text: str,
) -> int:
    """
    Estimate how many SEC heading markers appear
    inside a text container.

    This prevents us from promoting a tiny heading
    into a very large parent <div> containing multiple
    different sections.
    """

    if not text:
        return 0

    upper_text = " ".join(
        text.split()
    ).upper()

    matches = re.findall(
        r"\b(?:"
        r"PART\s+[IVX]+"
        r"|"
        r"ITEM\s+\d+[A-Z]?"
        r")\b",
        upper_text,
    )

    return len(
        matches
    )


# =========================================================
# FIND BEST HEADING CONTAINER
# =========================================================

def _promote_heading_container(
    element: Tag,
) -> Tag:
    """
    Expand a small heading element to a nearby parent
    only when that parent still represents ONE short
    SEC heading.

    Example:

        <div>
            <span>Item 1.</span>
            <span>Financial Statements</span>
        </div>

    The <div> contains a better complete heading than
    the first <span>, so we promote to the <div>.

    But we refuse to promote into a large container
    containing multiple ITEM/PART sections.
    """

    current = element


    while True:

        parent = current.parent


        if not _is_valid_tag(
            parent
        ):
            break


        parent_name = (
            parent.name or ""
        ).lower()


        if (
            parent_name
            not in PROMOTABLE_HEADING_CONTAINERS
        ):
            break


        parent_text = _clean_text(
            parent.get_text(
                " ",
                strip=True,
            )
        )


        if not parent_text:
            break


        if len(parent_text) > 250:
            break


        if not _looks_like_sec_heading(
            parent_text
        ):
            break


        # A heading container should describe only
        # one PART/ITEM heading.
        if _count_heading_markers(
            parent_text
        ) > 1:
            break


        current = parent


    return current


# =========================================================
# COLLECT SUPPLEMENTAL SEC HEADINGS
# =========================================================

def _collect_supplemental_headings(
    soup: BeautifulSoup,
) -> dict:
    """
    Find SEC headings represented using span/div/b/font/
    td/etc. rather than traditional heading/paragraph tags.

    Returns:

        {
            id(html_element): "Item 2. Management's ...",
            ...
        }

    Using the element id lets the main parser preserve
    document order without globally extracting every
    <div> and <span>.
    """

    heading_elements = {}


    candidates = soup.find_all(
        list(
            SUPPLEMENTAL_HEADING_TAGS
        )
    )


    for element in candidates:

        if not _is_valid_tag(
            element
        ):
            continue


        text = _clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )


        if not _looks_like_sec_heading(
            text
        ):
            continue


        canonical_element = (
            _promote_heading_container(
                element
            )
        )


        canonical_text = _clean_text(
            canonical_element.get_text(
                " ",
                strip=True,
            )
        )


        if not _looks_like_sec_heading(
            canonical_text
        ):
            continue


        heading_elements[
            id(
                canonical_element
            )
        ] = canonical_text


    return heading_elements


# =========================================================
# TABLE EXTRACTION
# =========================================================

def _extract_table_text(
    table: Tag,
) -> str:
    """
    Convert an HTML table into readable plain text.

    Example:

        Revenue | 2025 | 2024
        Europe  | 100  | 90
    """

    if not _is_valid_tag(
        table
    ):
        return ""

    rows = []


    for row in table.find_all(
        "tr"
    ):

        cells = row.find_all(
            [
                "th",
                "td",
            ]
        )


        cell_texts = []


        for cell in cells:

            if not _is_valid_tag(
                cell
            ):
                continue


            cell_text = _clean_text(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )


            if cell_text:

                cell_texts.append(
                    cell_text
                )


        if cell_texts:

            rows.append(
                " | ".join(
                    cell_texts
                )
            )


    return "\n".join(
        rows
    )


# =========================================================
# MAIN SEC PARSER
# =========================================================

def parse_sec_filing(
    content: bytes,
) -> dict:
    """
    Parse one SEC XHTML / iXBRL filing.

    Input:
        Raw filing bytes from GCS RAW.

    Output:
        {
            "title": ...,
            "full_text": ...,
            "blocks": [...],
            "statistics": {...}
        }

    The original RAW document is never modified.

    Parser strategy:

    1. Preserve the existing paragraph/list/table parser.
    2. Detect additional SEC headings represented through
       span/div/b/strong/font/td/th elements.
    3. Do NOT extract every div/span as narrative text,
       because nested SEC HTML would create huge duplicate
       blocks.
    """


    # =====================================================
    # 1. PARSE RAW SEC DOCUMENT
    # =====================================================

    soup = BeautifulSoup(
        content,
        "lxml",
    )


    # =====================================================
    # 2. CAPTURE DOCUMENT TITLE
    # =====================================================

    title = ""


    if soup.title:

        title = _clean_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )


    # =====================================================
    # 3. REMOVE OBVIOUS NON-CONTENT ELEMENTS
    # =====================================================

    removable_tags = [
        "script",
        "style",
        "noscript",
        "meta",
        "link",
    ]


    for tag_name in removable_tags:

        elements = list(
            soup.find_all(
                tag_name
            )
        )


        for element in elements:

            if _is_valid_tag(
                element
            ):
                element.extract()


    # =====================================================
    # 4. REMOVE HIDDEN iXBRL TECHNICAL CONTENT
    # =====================================================

    ixbrl_elements = []


    for element in soup.find_all():

        if not _is_valid_tag(
            element
        ):
            continue


        element_name = (
            element.name or ""
        ).lower()


        if element_name in {
            "ix:hidden",
            "ix:header",
        }:

            ixbrl_elements.append(
                element
            )


    for element in ixbrl_elements:

        element.extract()


    # =====================================================
    # 5. REMOVE CSS-HIDDEN CONTENT
    # =====================================================

    hidden_elements = []


    for element in soup.find_all():

        if _is_hidden(
            element
        ):

            hidden_elements.append(
                element
            )


    for element in hidden_elements:

        element.extract()


    # =====================================================
    # 6. EXTRACT HIGH-RECALL VISIBLE TEXT
    # =====================================================

    full_text = _clean_text(
        soup.get_text(
            "\n",
            strip=True,
        )
    )


    # =====================================================
    # 7. DISCOVER MODERN/LEGACY SEC HEADING ELEMENTS
    # =====================================================

    supplemental_headings = (
        _collect_supplemental_headings(
            soup
        )
    )


    # =====================================================
    # 8. EXTRACT STRUCTURED BLOCKS
    # =====================================================

    blocks = []

    heading_count = 0
    paragraph_count = 0
    list_item_count = 0
    table_count = 0

    supplemental_heading_count = 0


    # We deliberately search only the normal production
    # block tags plus tags that can contain supplemental
    # headings.
    #
    # Supplemental div/span/etc. elements are NOT emitted
    # unless they were positively identified as headings.
    meaningful_tags = soup.find_all(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "li",
            "table",
            "div",
            "span",
            "b",
            "strong",
            "font",
            "td",
            "th",
            "a",
        ]
    )


    previous_text = None


    for element in meaningful_tags:

        if not _is_valid_tag(
            element
        ):
            continue


        element_name = (
            element.name or ""
        ).lower()


        is_supplemental_heading = (
            id(
                element
            )
            in supplemental_headings
        )


        # -------------------------------------------------
        # Skip supplemental tags unless they have been
        # explicitly identified as SEC headings.
        # -------------------------------------------------

        if (
            element_name
            not in STANDARD_BLOCK_TAGS
            and
            not is_supplemental_heading
        ):
            continue


        # -------------------------------------------------
        # Avoid extracting normal paragraphs/list items
        # separately when they are inside tables.
        #
        # EXCEPTION:
        # A positively identified SEC heading is allowed
        # through even when it sits inside a layout table.
        # -------------------------------------------------

        if (
            element_name != "table"
            and
            element.find_parent(
                "table"
            )
            and
            not is_supplemental_heading
            and
            element_name
            not in TRUE_HEADING_TAGS
        ):

            continue


        # -------------------------------------------------
        # TABLE
        # -------------------------------------------------

        if element_name == "table":

            block_text = (
                _extract_table_text(
                    element
                )
            )

            block_type = "table"


        # -------------------------------------------------
        # TRUE HTML HEADING
        # -------------------------------------------------

        elif (
            element_name
            in TRUE_HEADING_TAGS
        ):

            block_text = _clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            block_type = "heading"


        # -------------------------------------------------
        # SUPPLEMENTAL SEC HEADING
        # -------------------------------------------------

        elif is_supplemental_heading:

            block_text = (
                supplemental_headings[
                    id(
                        element
                    )
                ]
            )

            block_type = "heading"

            supplemental_heading_count += 1


        # -------------------------------------------------
        # LIST ITEM
        # -------------------------------------------------

        elif element_name == "li":

            block_text = _clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            block_type = "list_item"


        # -------------------------------------------------
        # PARAGRAPH
        # -------------------------------------------------

        elif element_name == "p":

            block_text = _clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )


            if _looks_like_sec_heading(
                block_text
            ):

                block_type = "heading"

            else:

                block_type = "paragraph"


        else:

            continue


        # -------------------------------------------------
        # IGNORE EMPTY BLOCKS
        # -------------------------------------------------

        if not block_text:
            continue


        # -------------------------------------------------
        # IGNORE IMMEDIATE DUPLICATES
        # -------------------------------------------------

        if block_text == previous_text:
            continue


        # -------------------------------------------------
        # STORE BLOCK
        # -------------------------------------------------

        blocks.append(
            {
                "type": block_type,
                "text": block_text,
            }
        )


        # -------------------------------------------------
        # UPDATE STATISTICS
        # -------------------------------------------------

        if block_type == "heading":

            heading_count += 1


        elif block_type == "paragraph":

            paragraph_count += 1


        elif block_type == "list_item":

            list_item_count += 1


        elif block_type == "table":

            table_count += 1


        previous_text = block_text


    # =====================================================
    # 9. BUILD PARSER STATISTICS
    # =====================================================

    statistics = {

        "raw_bytes": len(
            content
        ),

        "visible_characters": len(
            full_text
        ),

        "blocks": len(
            blocks
        ),

        "headings": heading_count,

        "paragraphs": paragraph_count,

        "list_items": list_item_count,

        "tables": table_count,

        "supplemental_headings": (
            supplemental_heading_count
        ),
    }


    # =====================================================
    # 10. RETURN PARSED DOCUMENT
    # =====================================================

    return {

        "title": title,

        "full_text": full_text,

        "blocks": blocks,

        "statistics": statistics,
    }