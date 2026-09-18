import json

from google.cloud import storage


class GCSStorage:
    """
    Handles reading and writing objects
    in Google Cloud Storage.

    This class is deliberately storage focused.

    Other parts of the application use this
    class to interact with GCS.
    """

    def __init__(
        self,
        project_id: str,
        bucket_name: str,
    ):
        """
        Connect to one GCS bucket.
        """

        self.client = storage.Client(
            project=project_id
        )

        self.bucket = self.client.bucket(
            bucket_name
        )

    # ---------------------------------------------------------
    # CHECK WHETHER OBJECT EXISTS - if file is already ingested, don't re ingest it
    #That's why 1,000-document run reported:

    # New filings ingested: 900
    # Existing filings skipped: 100
    # Called idempotency
    #Running the same pipeline again should not corrupt or unnecessarily duplicate the data.
    # ---------------------------------------------------------

    def object_exists(
        self,
        destination_path: str,
    ) -> bool:
        """
        Check whether an object already exists
        inside this bucket.
        """

        blob = self.bucket.blob(
            destination_path
        )

        return blob.exists(
            client=self.client
        )

    # ---------------------------------------------------------
    # LIST OBJECTS
    # ---------------------------------------------------------

    def list_objects(
        self,
        prefix: str = "",
    ) -> list[str]:
        """
        List object names inside the bucket.

        The optional prefix allows us to limit
        the search to a specific logical folder.

        Example:

        prefix="sec/0000320193/"
        """

        blobs = self.client.list_blobs(
            self.bucket,
            prefix=prefix,
        )

        return [
            blob.name
            for blob in blobs
        ]

    # ---------------------------------------------------------
    # DOWNLOAD RAW BYTES
    # ---------------------------------------------------------

    def download_bytes(
        self,
        source_path: str,
    ) -> bytes:
        """
        Download an object from GCS
        as raw bytes.

        This is what we will use for
        original SEC XHTML/iXBRL filings.
        """

        blob = self.bucket.blob(
            source_path
        )

        return blob.download_as_bytes()

    # ---------------------------------------------------------
    # DOWNLOAD JSON
    # ---------------------------------------------------------

    def download_json(
        self,
        source_path: str,
    ) -> dict:
        """
        Download a JSON object from GCS
        and return it as a Python dictionary.
        """

        blob = self.bucket.blob(
            source_path
        )

        json_content = (
            blob.download_as_text()
        )

        return json.loads(
            json_content
        )

    # ---------------------------------------------------------
    # UPLOAD RAW BYTES - Used to upload the actual SEC filing.
    # ---------------------------------------------------------

    def upload_bytes(
        self,
        content: bytes,
        destination_path: str,
        content_type: str,
    ) -> None:
        """
        Upload raw bytes to GCS.
        """

        blob = self.bucket.blob(
            destination_path
        )

        blob.upload_from_string(
            content,
            content_type=content_type,
        )

    # ---------------------------------------------------------
    # UPLOAD TEXT
    # ---------------------------------------------------------

    def upload_text(
        self,
        content: str,
        destination_path: str,
        content_type: str = "text/plain",
    ) -> None:
        """
        Upload plain text to GCS.

        Day 2 will use this for normalized
        document text.
        """

        blob = self.bucket.blob(
            destination_path
        )

        blob.upload_from_string(
            content,
            content_type=content_type,
        )

    # ---------------------------------------------------------
    # UPLOAD JSON - used to upload manifest.json
    # ---------------------------------------------------------

    def upload_json(
        self,
        data: dict,
        destination_path: str,
    ) -> None:
        """
        Upload a Python dictionary or JSON-compatible
        object to GCS.
        """

        json_content = json.dumps(
            data,
            indent=2,
        )

        blob = self.bucket.blob(
            destination_path
        )

        blob.upload_from_string(
            json_content,
            content_type="application/json",
        )


# Why upload the manifest last?

# This was intentional.

# Imagine:

# upload filing is uploaded

# computer crashes

# upload manifest is not uploaded

# When the job reruns:

# manifest missing

# so we don't treat that filing as completed.

# Our manifest therefore acts as a simple:

# completion marker

# Conceptually:

# filing present
# +
# manifest present
# =
# completed ingestion