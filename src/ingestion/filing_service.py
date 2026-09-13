def extract_filings(
    submissions: dict,
    allowed_forms: set[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Extract recent SEC filings from the submissions response.

    Parameters
    ----------
    submissions:
        Raw company submissions JSON returned by the SEC.

    allowed_forms:
        Optional set of filing types to keep,
        for example {"10-K", "10-Q", "8-K"}.

    limit:
        Optional maximum number of filings to return.

    Returns
    -------
    list[dict]
        Clean list of filing records.
    """

    recent = submissions["filings"]["recent"]

    filings = []

    for i in range(len(recent["accessionNumber"])):

        form = recent["form"][i]

        # Skip filing types we do not want
        if allowed_forms is not None and form not in allowed_forms:
            continue

        filing = {
            "accession_number": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i],
            "form": form,
            "primary_document": recent["primaryDocument"][i],
        }

        filings.append(filing)

        # Stop once we have enough filings
        if limit is not None and len(filings) >= limit:
            break

    return filings