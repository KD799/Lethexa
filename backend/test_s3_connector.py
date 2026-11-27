
from moto import mock_aws
import boto3

from app.connectors.s3_connector import S3Connector


@mock_aws
def test_s3_connector():

    # Create simulated S3 bucket
    s3 = boto3.client(
        "s3",
        region_name="us-east-1"
    )

    s3.create_bucket(
        Bucket="cybershield-test-bucket"
    )

    # Upload synthetic test file
    s3.put_object(
        Bucket="cybershield-test-bucket",
        Key="customers.txt",
        Body="Name: Rahul\nEmail: rahul@example.com\nPhone: 9876543210",
        ContentType="text/plain"
    )

    # Connect our CyberShield connector
    connector = S3Connector()

    # Test listing
    files = connector.list_files(
        "cybershield-test-bucket"
    )

    print("\nFILES:", files)

    # Test reading
    content = connector.read_file(
        "cybershield-test-bucket",
        "customers.txt"
    )

    print("\nFILE CONTENT:\n", content)

    # Test metadata
    metadata = connector.get_file_metadata(
        "cybershield-test-bucket",
        "customers.txt"
    )

    print("\nMETADATA:", metadata)


if __name__ == "__main__":
    test_s3_connector()
