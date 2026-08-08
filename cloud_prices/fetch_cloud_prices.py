"""
Fetch cloud pricing for AWS (ap-south-1, ap-southeast-1) and Azure (Central
India, Southeast Asia), expanding each instance family across 4 sizes
(large->4xlarge on AWS, 2->16 vCPU on Azure).

Requires: boto3, requests (AWS credentials configured; Azure needs no auth).
Usage: python fetch_cloud_prices.py
"""

import csv
import json
import boto3
import requests

# Region mappings
AWS_REGIONS = {
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
}
AZURE_REGIONS = ["centralindia", "southeastasia"]

# Each AWS family maps to an Azure family template; {n} = vCPU count.
SIZE_LADDER = {          # aws suffix : vCPUs
    "large":   2,
    "xlarge":  4,
    "2xlarge": 8,
    "4xlarge": 16,
}

FAMILIES = [
    # (aws_family, azure_template)
    ("m5",  "Standard_D{n}s_v3"),    # Intel GP
    ("c5",  "Standard_F{n}s_v2"),    # Intel compute
    ("m5a", "Standard_D{n}as_v4"),   # AMD GP
    ("m6i", "Standard_D{n}s_v5"),    # Intel Ice Lake GP
    ("c6i", "Standard_D{n}ls_v5"),   # Intel Ice Lake, 2:1 mem ratio
    ("c5a", "Standard_D{n}as_v5"),   # AMD v5
]

AZURE_EXTRA_TEMPLATES = [
    "Standard_D{n}ds_v4",             # Intel GP with local temp disk
]


def get_aws_ondemand_price(instance_type: str, location_name: str) -> float | None:
    client = boto3.client("pricing", region_name="us-east-1")
    resp = client.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location_name},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        ],
        MaxResults=1,
    )
    if not resp["PriceList"]:
        return None
    product = json.loads(resp["PriceList"][0])
    for term in product["terms"]["OnDemand"].values():
        for dim in term["priceDimensions"].values():
            return float(dim["pricePerUnit"]["USD"])
    return None


def get_aws_spot_prices(instance_type: str, region_code: str) -> dict[str, float]:
    ec2 = boto3.client("ec2", region_name=region_code)
    resp = ec2.describe_spot_price_history(
        InstanceTypes=[instance_type],
        ProductDescriptions=["Linux/UNIX"],
        MaxResults=20,
    )
    prices: dict[str, float] = {}
    for entry in resp["SpotPriceHistory"]:
        prices.setdefault(entry["AvailabilityZone"], float(entry["SpotPrice"]))
    return prices


def get_azure_vm_prices(vm_size: str, arm_region: str) -> list[dict]:
    url = "https://prices.azure.com/api/retail/prices"
    query = (
        f"serviceName eq 'Virtual Machines' "
        f"and armRegionName eq '{arm_region}' "
        f"and armSkuName eq '{vm_size}' "
        f"and priceType eq 'Consumption'"
    )
    results, next_url = [], f"{url}?$filter={query}"
    while next_url:
        data = requests.get(next_url, timeout=30).json()
        results.extend(data.get("Items", []))
        next_url = data.get("NextPageLink")
    return [
        {
            "meter": item["meterName"],
            "price_usd_per_hr": item["retailPrice"],
        }
        for item in results
        if "Windows" not in item["productName"]
    ]


if __name__ == "__main__":
    aws_rows, azure_rows = [], []

    for aws_family, azure_template in FAMILIES:
        for aws_suffix, vcpus in SIZE_LADDER.items():
            aws_type = f"{aws_family}.{aws_suffix}"
            azure_size = azure_template.format(n=vcpus)
            print(f"\n--- {aws_type}  /  {azure_size} ---")

            # AWS: on-demand + spot, both regions
            for region_code, location_name in AWS_REGIONS.items():
                od = get_aws_ondemand_price(aws_type, location_name)
                if od is not None:
                    print(f"  AWS {region_code} on-demand: ${od}/hr")
                    aws_rows.append({"region": region_code, "availability_zone": "",
                                     "instance_type": aws_type, "vcpus": vcpus,
                                     "tier": "on-demand", "price_usd_hr": od})
                else:
                    print(f"  AWS {region_code} on-demand: not found")

                for az, price in sorted(get_aws_spot_prices(aws_type, region_code).items()):
                    aws_rows.append({"region": region_code, "availability_zone": az,
                                     "instance_type": aws_type, "vcpus": vcpus,
                                     "tier": "spot", "price_usd_hr": price})

            # Azure: both regions
            for arm_region in AZURE_REGIONS:
                items = get_azure_vm_prices(azure_size, arm_region)
                if not items:
                    print(f"  Azure {arm_region}: no prices found")
                for item in items:
                    azure_rows.append({"region": arm_region, "vm_size": azure_size,
                                       "vcpus": vcpus, "tier": item["meter"],
                                       "price_usd_hr": item["price_usd_per_hr"]})

    for azure_template in AZURE_EXTRA_TEMPLATES:
        for vcpus in SIZE_LADDER.values():
            azure_size = azure_template.format(n=vcpus)
            print(f"\n--- Azure extra / {azure_size} ---")
            for arm_region in AZURE_REGIONS:
                items = get_azure_vm_prices(azure_size, arm_region)
                if not items:
                    print(f"  Azure {arm_region}: no prices found")
                for item in items:
                    azure_rows.append({"region": arm_region, "vm_size": azure_size,
                                       "vcpus": vcpus, "tier": item["meter"],
                                       "price_usd_hr": item["price_usd_per_hr"]})

    with open("aws_prices.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region", "availability_zone", "instance_type",
                                          "vcpus", "tier", "price_usd_hr"])
        w.writeheader()
        w.writerows(aws_rows)

    with open("azure_prices.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region", "vm_size", "vcpus", "tier", "price_usd_hr"])
        w.writeheader()
        w.writerows(azure_rows)

    od_count = sum(1 for r in aws_rows if r["tier"] == "on-demand")
    print(f"\nSaved {len(aws_rows)} rows to aws_prices.csv ({od_count} on-demand)")
    print(f"Saved {len(azure_rows)} rows to azure_prices.csv")