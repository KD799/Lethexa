
import boto3
from botocore.exceptions import ClientError


class S3Connector:

    def __init__(self, endpoint_url=None):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )

    def list_files(self, bucket_name):
        try:
            response = self.s3.list_objects_v2(
                Bucket=bucket_name
            )

            files = []

            for obj in response.get("Contents", []):
                files.append({
                    "file_name": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat()
                })

            return files

        except ClientError as error:
            raise ValueError(
                f"Unable to list S3 files: {error}"
            )

    def read_file(self, bucket_name, file_name):
        try:
            response = self.s3.get_object(
                Bucket=bucket_name,
                Key=file_name
            )

            content = response["Body"].read().decode(
                "utf-8",
                errors="replace"
            )

            return content

        except ClientError as error:
            raise ValueError(
                f"Unable to read S3 file: {error}"
            )

    def get_file_metadata(self, bucket_name, file_name):
        try:
            response = self.s3.head_object(
                Bucket=bucket_name,
                Key=file_name
            )

            return {
                "file_name": file_name,
                "size": response["ContentLength"],
                "content_type": response.get(
                    "ContentType",
                    "unknown"
                ),
                "last_modified": response["LastModified"].isoformat()
            }

        except ClientError as error:
            raise ValueError(
                f"Unable to get file metadata: {error}"
            )
