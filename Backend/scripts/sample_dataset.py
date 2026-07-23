"""
Carves out a random test sample from your full feedback dataset,
so you can test the batched Gemini pipeline (and check for Render
timeouts) before running the entire 20k-review file.

Usage:
    python sample_dataset.py <input_file> <sample_size>

Example:
    python sample_dataset.py zomato_reviews_full.csv 1000
"""

import sys
import pandas as pd
from pathlib import Path


def sample_dataset(input_path: str, sample_size: int, seed: int = 42):
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(input_path)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(input_path, sheet_name=0)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    total_rows = len(df)
    print(f"Loaded {total_rows} total rows from {input_path.name}")

    if sample_size >= total_rows:
        print("Sample size >= total rows, using the full file as-is.")
        sample_df = df
    else:
        # Random sample (not just the first N rows) so it reflects the
        # real duplicate/variety distribution across the whole dataset.
        sample_df = df.sample(n=sample_size, random_state=seed).reset_index(drop=True)

    output_name = f"{input_path.stem}_sample_{sample_size}{input_path.suffix}"
    output_path = input_path.parent / output_name

    if suffix == ".csv":
        sample_df.to_csv(output_path, index=False)
    else:
        sample_df.to_excel(output_path, index=False)

    print(f"Wrote {len(sample_df)} rows to {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python sample_dataset.py <input_file> <sample_size>")
        sys.exit(1)

    input_file = sys.argv[1]
    n = int(sys.argv[2])
    sample_dataset(input_file, n)