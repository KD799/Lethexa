
import boto3
from moto import mock_aws

from app.connectors.s3_connector import S3Connector
from app.services.s3_pii_scanner import detect_pii


@mock_aws
def test_s3_pii_scanner():

    # Create simulated S3 bucket
    s3 = boto3.client("s3", region_name="us-east-1")

    s3.create_bucket(
        Bucket="cybershield-pii-test"
    )

    # Upload synthetic customer data
    sample_data = """
    Name: Rahul
    Email: rahul@example.com
    Phone: 9876543210
    """

    s3.put_object(
        Bucket="cybershield-pii-test",
        Key="customers.txt",
        Body=sample_data,
        ContentType="text/plain"
    )

    # Read file using CyberShield S3 connector
    connector = S3Connector()

    content = connector.read_file(
        "cybershield-pii-test",
        "customers.txt"
    )

    # Scan file for PII
    result = detect_pii(content)

    print("\nCYBERSHIELD S3 PII SCAN REPORT")
    print("--------------------------------")
    print("File: customers.txt")
    print("PII Found:", result["contains_pii"])
    print("Categories:", result["total_pii_categories"])
    print("Findings:", result["findings"])


if __name__ == "__main__":
    test_s3_pii_scanner()
