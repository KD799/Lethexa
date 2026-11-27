
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:5000",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

bucket = "cybershield-discovery-test"

s3.create_bucket(Bucket=bucket)

sample_data = """
Name: Rahul Sharma
Email: rahul@example.com
Phone: 9876543210
Aadhaar: 1234 5678 9012
"""

s3.put_object(
    Bucket=bucket,
    Key="customers.txt",
    Body=sample_data,
    ContentType="text/plain"
)

s3.put_object(
    Bucket=bucket,
    Key="public.txt",
    Body="Welcome to CyberShield. No personal information here.",
    ContentType="text/plain"
)

print("Test S3 bucket created successfully!")
print("Bucket:", bucket)
