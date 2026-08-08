import os
import boto3
from botocore.config import Config
from azure.storage.blob import BlobServiceClient

# Configuration

AWS_BUCKET = "cost-aware-spark-research-manoj-2026"
AWS_PREFIX = "spark-workloads/scripts/"

AZURE_CONTAINER = "scripts"

# AWS Client

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_REGION", "ap-south-1"),
    config=Config(
        retries={
            "max_attempts": 10,
            "mode": "standard"
        }
    )
)

# Azure Client

connection_string = (
    f"DefaultEndpointsProtocol=https;"
    f"AccountName={os.environ['AZURE_STORAGE_ACCOUNT']};"
    f"AccountKey={os.environ['AZURE_STORAGE_KEY']};"
    f"EndpointSuffix=core.windows.net"
)

blob_service = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service.get_container_client(AZURE_CONTAINER)

if not container_client.exists():
    raise Exception(f"Container '{AZURE_CONTAINER}' does not exist.")

print(f"Connected to Azure container: {AZURE_CONTAINER}")
print("Scanning S3 scripts folder...\n")

uploaded = 0

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(
    Bucket=AWS_BUCKET,
    Prefix=AWS_PREFIX
):

    if "Contents" not in page:
        continue

    for obj in page["Contents"]:

        key = obj["Key"]
 
        # Skip folder entries
        if key.endswith("/"):
            continue

        # Preserve the scripts folder
        blob_name = key[len(AWS_PREFIX):]

        print(f"Copying: {key} -> {blob_name}")

        response = s3.get_object(
            Bucket=AWS_BUCKET,
            Key=key
        )

        blob_client = container_client.get_blob_client(blob_name)

        blob_client.upload_blob(
            response["Body"],
            overwrite=True
        )

        uploaded += 1

print("\n===================================")
print("Transfer Complete")
print("===================================")
print(f"Uploaded {uploaded} files.")