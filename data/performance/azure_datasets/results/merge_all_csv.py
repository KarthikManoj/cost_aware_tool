from pathlib import Path
import pandas as pd

# Folder containing all downloaded CSVs
input_folder = Path(".")

# Find all CSV files (including subfolders)
csv_files = list(input_folder.rglob("*.csv"))

print(f"Found {len(csv_files)} CSV files")

dfs = []

for file in csv_files:
    try:
        df = pd.read_csv(file)

        # Optional: record the source file
        df["source_file"] = file.name

        dfs.append(df)

    except Exception as e:
        print(f"Skipping {file}: {e}")

merged_df = pd.concat(dfs, ignore_index=True)

output_file = input_folder / "merged_azure_results.csv"
merged_df.to_csv(output_file, index=False)

print(f"Merged {len(csv_files)} files")
print(f"Rows: {len(merged_df)}")
print(f"Saved to: {output_file}")