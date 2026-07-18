import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from azure.storage.blob import BlobServiceClient
from tqdm import tqdm

# ============================================================
# CONFIGURATION
# ============================================================

AWS_BUCKET = "cost-aware-spark-research-manoj-2026"
AWS_PREFIX = "spark-workloads/data/"

AZURE_STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
AZURE_STORAGE_KEY = os.environ["AZURE_STORAGE_KEY"]
AZURE_CONTAINER = "datasets"

# ============================================================
# CONNECT TO AWS
# ============================================================

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

# ============================================================
# CONNECT TO AZURE
# ============================================================

connection_string = (
    f"DefaultEndpointsProtocol=https;"
    f"AccountName={AZURE_STORAGE_ACCOUNT};"
    f"AccountKey={AZURE_STORAGE_KEY};"
    f"EndpointSuffix=core.windows.net"
)

blob_service = BlobServiceClient.from_connection_string(connection_string)
container = blob_service.get_container_client(AZURE_CONTAINER)

# ============================================================
# COPY FILES
# ============================================================

uploaded = 0
failed = 0
total_size = 0

print("\nScanning S3...\n")

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(
    Bucket=AWS_BUCKET,
    Prefix=AWS_PREFIX
):

    if "Contents" not in page:
        continue

    for obj in tqdm(page["Contents"]):

        key = obj["Key"]

        if key.endswith("/"):
            continue

        blob_name = key[len(AWS_PREFIX):]

        try:

            response = s3.get_object(
                Bucket=AWS_BUCKET,
                Key=key
            )

            blob = container.get_blob_client(blob_name)

            blob.upload_blob(
                response["Body"],
                overwrite=True
            )

            uploaded += 1
            total_size += obj["Size"]

        except ClientError as e:

            failed += 1
            print(f"\nFailed: {key}")
            print(e)

# ============================================================
# SUMMARY
# ============================================================

print("\n==============================")
print("Transfer Completed")
print("==============================")

print(f"Uploaded Files : {uploaded}")
print(f"Failed Files   : {failed}")
print(f"Total Size     : {total_size / (1024**3):.2f} GB")