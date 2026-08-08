import pandas as pd

# File paths

AWS_FILE = "performance_dataset.csv"
AZURE_FILE = "merged_azure_results_clean.csv"

CARBON_FILE = "/Users/manojanbalagan/Documents/research/research/cost-aware-infrastructure-optimization/Carbon_dataset/carbon_intensity_daily.csv"
RENEWABLE_FILE = "/Users/manojanbalagan/Documents/research/research/cost-aware-infrastructure-optimization/Carbon_dataset/renewable_intensity_daily.csv"

OUTPUT_FILE = "cloud_carbon_model_dataset.csv"

# Load data

print("Loading datasets...")

aws = pd.read_csv(AWS_FILE)
azure = pd.read_csv(AZURE_FILE)

carbon = pd.read_csv(CARBON_FILE)
renewable = pd.read_csv(RENEWABLE_FILE)

# Standardize aws dataset

aws = aws.rename(columns={
    "instance_type": "machine_type"
})

# Standardize azure dataset

azure = azure.rename(columns={
    "VM_Size": "machine_type",
    "Dataset_Size_MB": "dataset_size_mb",
    "Runtime_Minutes": "runtime_minutes",
    "Cost_USD": "cost_usd",
    "Nodes": "nodes",
    "Region": "region",
    "Workload": "workload_type"
})

# Keep only required performance columns

performance_columns = [
    "cloud",
    "region",
    "electricity_zone",
    "dataset_size_mb",
    "workload_type",
    "machine_type",
    "nodes",
    "runtime_minutes",
    "cost_usd"
]

aws = aws[performance_columns]
azure = azure[performance_columns]

# Merge aws + azure

performance = pd.concat([aws, azure], ignore_index=True)

print("\nPerformance dataset shape:", performance.shape)

# Standardize carbon dataset column names

carbon = carbon.rename(columns={
    "Cloud": "cloud",
    "Region": "region",
    "Electricity_Zone": "electricity_zone",
    "Carbon_Intensity_gCO2eq_per_kWh": "carbon_intensity"
})

renewable = renewable.rename(columns={
    "Cloud": "cloud",
    "Region": "region",
    "Electricity_Zone": "electricity_zone",
    "Renewable_Percentage": "renewable_percentage"
})

# Normalize merge keys

def normalize_keys(df):
    df["cloud"] = (
        df["cloud"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["region"] = (
        df["region"]
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "", regex=False)
    )

    df["electricity_zone"] = (
        df["electricity_zone"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df

performance = normalize_keys(performance)
carbon = normalize_keys(carbon)
renewable = normalize_keys(renewable)

# Merge daily carbon data

carbon_daily = pd.merge(
    carbon,
    renewable,
    on=[
        "Date",
        "cloud",
        "region",
        "electricity_zone"
    ],
    how="inner"
)

print("Carbon daily dataset shape:", carbon_daily.shape)

# Calculate regional mean values

carbon_summary = (
    carbon_daily
    .groupby(
        [
            "cloud",
            "region",
            "electricity_zone"
        ],
        as_index=False
    )
    .agg(
        carbon_intensity_mean=("carbon_intensity", "mean"),
        renewable_percentage_mean=("renewable_percentage", "mean")
    )
)

print("Carbon summary shape:", carbon_summary.shape)

# Display unique values

print("\n===== PERFORMANCE =====")
print("Cloud:", performance["cloud"].unique())
print("Region:", performance["region"].unique())
print("Electricity Zone:", performance["electricity_zone"].unique())

print("\n===== CARBON SUMMARY =====")
print("Cloud:", carbon_summary["cloud"].unique())
print("Region:", carbon_summary["region"].unique())
print("Electricity Zone:", carbon_summary["electricity_zone"].unique())

# Merge performance + carbon

final_dataset = pd.merge(
    performance,
    carbon_summary,
    on=[
        "cloud",
        "region",
        "electricity_zone"
    ],
    how="left"
)

# Check for missing values

print("\nMissing values")
print(final_dataset.isnull().sum())

# Save final dataset

final_dataset.to_csv(OUTPUT_FILE, index=False)

print("\n=====================================================")
print("Dataset created successfully!")
print("Rows :", len(final_dataset))
print("Columns :", len(final_dataset.columns))
print("Saved as:", OUTPUT_FILE)
print("=====================================================")

print("\nFinal Columns")
print(final_dataset.columns.tolist())

print("\nFirst 5 rows")
print(final_dataset.head())