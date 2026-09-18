import argparse
import csv
import json
import math
import random

from collections import Counter, defaultdict
from pathlib import Path


# =========================================================
# CONFIGURATION
# =========================================================

RISK_WEIGHTS = {
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
    "unknown_no_headings": 3.0,
}


# =========================================================
# ARGUMENTS
# =========================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Build a representative golden SEC "
            "regression sample from the corpus profile."
        )
    )

    parser.add_argument(
        "--input",
        default="reports/sec_corpus_profile.csv",
        help="Corpus profile CSV.",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Target golden sample size.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Reproducible random seed.",
    )

    parser.add_argument(
        "--output-csv",
        default="reports/golden_sample.csv",
    )

    parser.add_argument(
        "--output-json",
        default="reports/golden_sample.json",
    )

    return parser.parse_args()


# =========================================================
# HELPERS
# =========================================================

def ratio_bucket(value: float) -> str:

    if value == 0:
        return "0"

    if value <= 0.25:
        return "low"

    if value <= 0.75:
        return "medium"

    return "high"


def create_archetype(row: dict) -> str:
    """
    Create a broader parser-relevant archetype.

    We intentionally avoid using every HTML count.

    The goal is to group documents that require
    similar parser behavior.
    """

    heading_tag = (
        row.get("dominant_heading_tag")
        or "none"
    )

    heading_reach = ratio_bucket(
        float(
            row.get(
                "heading_reachable_ratio",
                0,
            )
            or 0
        )
    )

    heading_table = ratio_bucket(
        float(
            row.get(
                "heading_inside_table_ratio",
                0,
            )
            or 0
        )
    )

    p_count = int(
        float(
            row.get(
                "p_count",
                0,
            )
            or 0
        )
    )

    p_structure = (
        "present"
        if p_count > 0
        else "absent"
    )

    return (
        f"heading={heading_tag}"
        f"|reach={heading_reach}"
        f"|table={heading_table}"
        f"|p={p_structure}"
    )


# =========================================================
# LOAD PROFILE
# =========================================================

def load_profile(path: str) -> list[dict]:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(
            file
        )

        return list(
            reader
        )


# =========================================================
# DOCUMENT SELECTION SCORE
# =========================================================

def document_diversity_score(
    row: dict,
    global_ciks: set,
    archetype_forms: set,
    archetype_sizes: set,
    archetype_families: set,
    archetype_years: set,
) -> int:
    """
    Prefer documents that add new diversity.
    """

    score = 0


    if row["cik"] not in global_ciks:
        score += 10


    if row["form"] not in archetype_forms:
        score += 5


    if (
        row["size_bucket"]
        not in archetype_sizes
    ):
        score += 4


    if (
        row["structural_family"]
        not in archetype_families
    ):
        score += 3


    if row["year"] not in archetype_years:
        score += 2


    return score


# =========================================================
# MAIN
# =========================================================

def main():

    args = parse_arguments()


    rows = load_profile(
        args.input
    )


    if not rows:

        raise RuntimeError(
            "Corpus profile contains no documents."
        )


    sample_size = min(
        args.sample_size,
        len(rows),
    )


    rng = random.Random(
        args.seed
    )


    # =====================================================
    # ADD ARCHETYPE
    # =====================================================

    for row in rows:

        row["parser_archetype"] = (
            create_archetype(
                row
            )
        )


        # Reproducible random tie breaker
        row["_random_order"] = (
            rng.random()
        )


    # =====================================================
    # GROUP BY ARCHETYPE
    # =====================================================

    groups = defaultdict(
        list
    )


    for row in rows:

        groups[
            row["parser_archetype"]
        ].append(
            row
        )


    # =====================================================
    # TRACK SELECTION STATE
    # =====================================================

    selected = []

    selected_ids = set()

    global_ciks = set()


    archetype_selected_count = (
        Counter()
    )


    archetype_forms = defaultdict(
        set
    )

    archetype_sizes = defaultdict(
        set
    )

    archetype_families = defaultdict(
        set
    )

    archetype_years = defaultdict(
        set
    )


    # =====================================================
    # PICK ONE FROM EVERY ARCHETYPE FIRST
    # =====================================================

    archetypes = sorted(
        groups.keys(),
        key=lambda key: (
            -len(groups[key]),
            key,
        ),
    )


    for archetype in archetypes:

        if len(selected) >= sample_size:
            break


        candidates = groups[
            archetype
        ]


        candidates = sorted(
            candidates,
            key=lambda row: (
                -document_diversity_score(
                    row=row,
                    global_ciks=global_ciks,
                    archetype_forms=(
                        archetype_forms[
                            archetype
                        ]
                    ),
                    archetype_sizes=(
                        archetype_sizes[
                            archetype
                        ]
                    ),
                    archetype_families=(
                        archetype_families[
                            archetype
                        ]
                    ),
                    archetype_years=(
                        archetype_years[
                            archetype
                        ]
                    ),
                ),
                row[
                    "_random_order"
                ],
            ),
        )


        chosen = candidates[0]


        selected.append(
            chosen
        )

        selected_ids.add(
            chosen["document_id"]
        )

        global_ciks.add(
            chosen["cik"]
        )


        archetype_selected_count[
            archetype
        ] += 1


        archetype_forms[
            archetype
        ].add(
            chosen["form"]
        )


        archetype_sizes[
            archetype
        ].add(
            chosen["size_bucket"]
        )


        archetype_families[
            archetype
        ].add(
            chosen[
                "structural_family"
            ]
        )


        archetype_years[
            archetype
        ].add(
            chosen["year"]
        )


    # =====================================================
    # FILL REMAINING SAMPLE
    # =====================================================

    while len(selected) < sample_size:

        best_archetype = None

        best_priority = None


        for archetype, documents in (
            groups.items()
        ):

            available_count = sum(
                1
                for document in documents
                if (
                    document[
                        "document_id"
                    ]
                    not in selected_ids
                )
            )


            if available_count == 0:
                continue


            risks = Counter(
                document[
                    "current_parser_risk"
                ]
                for document in documents
            )


            dominant_risk = (
                risks.most_common(
                    1
                )[0][0]
            )


            risk_weight = (
                RISK_WEIGHTS.get(
                    dominant_risk,
                    1.0,
                )
            )


            population_weight = math.sqrt(
                len(documents)
            )


            already_selected = (
                archetype_selected_count[
                    archetype
                ]
            )


            priority = (
                population_weight
                *
                risk_weight
                /
                (
                    already_selected
                    +
                    1
                )
            )


            if (
                best_priority is None
                or
                priority > best_priority
            ):

                best_priority = priority

                best_archetype = (
                    archetype
                )


        if best_archetype is None:
            break


        candidates = [
            document
            for document in groups[
                best_archetype
            ]
            if (
                document["document_id"]
                not in selected_ids
            )
        ]


        candidates = sorted(
            candidates,
            key=lambda row: (
                -document_diversity_score(
                    row=row,
                    global_ciks=global_ciks,
                    archetype_forms=(
                        archetype_forms[
                            best_archetype
                        ]
                    ),
                    archetype_sizes=(
                        archetype_sizes[
                            best_archetype
                        ]
                    ),
                    archetype_families=(
                        archetype_families[
                            best_archetype
                        ]
                    ),
                    archetype_years=(
                        archetype_years[
                            best_archetype
                        ]
                    ),
                ),
                row[
                    "_random_order"
                ],
            ),
        )


        chosen = candidates[0]


        selected.append(
            chosen
        )


        selected_ids.add(
            chosen["document_id"]
        )


        global_ciks.add(
            chosen["cik"]
        )


        archetype_selected_count[
            best_archetype
        ] += 1


        archetype_forms[
            best_archetype
        ].add(
            chosen["form"]
        )


        archetype_sizes[
            best_archetype
        ].add(
            chosen["size_bucket"]
        )


        archetype_families[
            best_archetype
        ].add(
            chosen[
                "structural_family"
            ]
        )


        archetype_years[
            best_archetype
        ].add(
            chosen["year"]
        )


    # =====================================================
    # ADD SELECTION ORDER
    # =====================================================

    for index, row in enumerate(
        selected,
        start=1,
    ):

        row["selection_order"] = (
            index
        )


    # =====================================================
    # SUMMARY
    # =====================================================

    risk_distribution = Counter(
        row[
            "current_parser_risk"
        ]
        for row in selected
    )


    form_distribution = Counter(
        row["form"]
        for row in selected
    )


    size_distribution = Counter(
        row[
            "size_bucket"
        ]
        for row in selected
    )


    selected_archetypes = {
        row[
            "parser_archetype"
        ]
        for row in selected
    }


    selected_families = {
        row[
            "structural_family"
        ]
        for row in selected
    }


    selected_ciks = {
        row["cik"]
        for row in selected
    }


    summary = {
        "source_documents": (
            len(rows)
        ),

        "sample_size": (
            len(selected)
        ),

        "seed": (
            args.seed
        ),

        "unique_ciks": len(
            selected_ciks
        ),

        "archetypes_covered": len(
            selected_archetypes
        ),

        "structural_families_covered": len(
            selected_families
        ),

        "risk_distribution": dict(
            risk_distribution
        ),

        "form_distribution": dict(
            form_distribution
        ),

        "size_distribution": dict(
            size_distribution
        ),
    }


    # =====================================================
    # SAVE CSV
    # =====================================================

    output_csv = Path(
        args.output_csv
    )


    output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    csv_rows = []


    for row in selected:

        clean_row = {
            key: value
            for key, value in row.items()
            if key != "_random_order"
        }

        csv_rows.append(
            clean_row
        )


    fieldnames = list(
        csv_rows[0].keys()
    )


    with output_csv.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )


        writer.writeheader()

        writer.writerows(
            csv_rows
        )


    # =====================================================
    # SAVE JSON
    # =====================================================

    output_json = Path(
        args.output_json
    )


    output_json.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with output_json.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "summary": summary,
                "documents": csv_rows,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )


    # =====================================================
    # PRINT SHORT RESULT
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "GOLDEN SAMPLE CREATED"
    )

    print(
        "========================================"
    )


    print(
        f"\nDocuments: "
        f"{len(selected)}"
    )

    print(
        f"Unique CIKs: "
        f"{len(selected_ciks)}"
    )

    print(
        f"Archetypes covered: "
        f"{len(selected_archetypes)}"
    )

    print(
        f"Structural families covered: "
        f"{len(selected_families)}"
    )


    print(
        "\nRisk:"
    )

    for risk, count in (
        risk_distribution.items()
    ):

        print(
            f"  {risk}: {count}"
        )


    print(
        "\nForms:"
    )

    for form, count in (
        form_distribution.items()
    ):

        print(
            f"  {form}: {count}"
        )


    print(
        "\nFiles:"
    )

    print(
        f"  {output_csv}"
    )

    print(
        f"  {output_json}"
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()