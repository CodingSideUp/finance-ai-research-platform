import httpx

from tenacity import retry, stop_after_attempt, wait_exponential


class SECClient:
    """
    Client responsible for communicating with SEC EDGAR.

    Responsibilities:
    - Retrieve the SEC company universe.
    - Retrieve company filing metadata.
    - Build SEC filing archive URLs.
    - Download original SEC filing documents.
    """

    # ---------------------------------------------------------
    # SEC endpoints
    # ---------------------------------------------------------

    BASE_DATA_URL = "https://data.sec.gov"

    BASE_ARCHIVE_URL = (
        "https://www.sec.gov/Archives"
    )

    COMPANY_TICKERS_URL = (
        "https://www.sec.gov/files/company_tickers.json"
    )


    # ---------------------------------------------------------
    # Initialise reusable HTTP client
    # ---------------------------------------------------------

    def __init__(
        self,
        user_agent: str,
    ):
        """
        Create a reusable HTTP client for SEC requests.
        """

        if not user_agent:
            raise ValueError(
                "A valid SEC User-Agent must be provided."
            )

        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

        self.client = httpx.Client(
            headers=self.headers,
            timeout=30.0,
        )


    # ---------------------------------------------------------
    # Retrieve SEC company universe
    # ---------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
    )
    def get_company_tickers(
        self,
    ) -> dict:
        """
        Retrieve the SEC company ticker dataset.

        The response contains company names,
        ticker symbols and CIK numbers.

        This allows us to move from one hardcoded
        company to multi-company ingestion.
        """

        response = self.client.get(
            self.COMPANY_TICKERS_URL
        )

        response.raise_for_status()

        return response.json()


    # ---------------------------------------------------------
    # Retrieve filing metadata for one company
    # ---------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
    )
    def get_company_submissions(
        self,
        cik: str,
    ) -> dict:
        """
        Retrieve SEC filing metadata for one company.
        """

        cik = cik.zfill(10)

        url = (
            f"{self.BASE_DATA_URL}/submissions/"
            f"CIK{cik}.json"
        )

        response = self.client.get(
            url
        )

        response.raise_for_status()

        return response.json()


    # ---------------------------------------------------------
    # Build URL for actual SEC filing
    # ---------------------------------------------------------

    def build_filing_url(
        self,
        cik: str,
        accession_number: str,
        primary_document: str,
    ) -> str:
        """
        Build the SEC EDGAR archive URL
        for a particular filing.
        """

        # SEC archive URLs use CIK without leading zeros.
        cik_without_leading_zeros = str(
            int(cik)
        )

        # SEC archive paths use accession number
        # without hyphens.
        accession_without_hyphens = (
            accession_number.replace(
                "-",
                "",
            )
        )

        return (
            f"{self.BASE_ARCHIVE_URL}/edgar/data/"
            f"{cik_without_leading_zeros}/"
            f"{accession_without_hyphens}/"
            f"{primary_document}"
        )


    # ---------------------------------------------------------
    # Download actual SEC filing
    # ---------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
    )
    def download_filing(
        self,
        url: str,
    ) -> bytes:
        """
        Download an original SEC filing
        as raw bytes.
        """

        response = self.client.get(
            url
        )

        response.raise_for_status()

        return response.content


    # ---------------------------------------------------------
    # Close HTTP client
    # ---------------------------------------------------------

    def close(
        self,
    ) -> None:
        """
        Close the reusable HTTP client.
        """

        self.client.close()