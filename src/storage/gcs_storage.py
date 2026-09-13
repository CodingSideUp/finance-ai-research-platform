import json

from google.cloud import storage


class GCSStorage:
    """
    Handles reading and writing objects
    in Google Cloud Storage.
    """

    def __init__(
        self,
        project_id: str,
        bucket_name: str,
    ):
        self.client = storage.Client(
            project=project_id
        )

        self.bucket = self.client.bucket(
            bucket_name
        )

    def object_exists(
        self,
        destination_path: str,
    ) -> bool:
        """
        Check whether an object already exists in GCS.

        This is used to make ingestion idempotent.
        """

        blob = self.bucket.blob(
            destination_path
        )

        return blob.exists(
            client=self.client
        )

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

    def upload_json(
        self,
        data: dict,
        destination_path: str,
    ) -> None:
        """
        Upload a Python dictionary as JSON.
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