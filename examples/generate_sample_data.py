"""Generate a deliberately messy customer dataset for demos.

Every quality check has something to find here: missing values, duplicate rows,
a primary-key collision, schema/type drift, out-of-range values, an invalid
category, outliers, and a constant column. Run it, then point the engine at the
output to see the full report light up.

    python examples/generate_sample_data.py
    python -m dqe assess examples/data/customers.csv --config config.example.yaml
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Seeded for reproducibility — the same "mess" every run, which matters for
# screenshots and video.
RNG = np.random.default_rng(42)
N = 1000

OUT = Path(__file__).parent / "data" / "customers.csv"


def generate() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "customer_id": range(1, N + 1),
            "signup_date": pd.to_datetime("2024-01-01")
            + pd.to_timedelta(RNG.integers(0, 540, N), unit="D"),
            "age": RNG.normal(42, 13, N).round().astype(int),
            "country": RNG.choice(["US", "CA", "GB", "DE", "FR"], N, p=[.4, .2, .2, .1, .1]),
            "plan": RNG.choice(["free", "pro", "enterprise"], N, p=[.6, .3, .1]),
            "status": RNG.choice(["active", "churned", "trial"], N, p=[.7, .2, .1]),
            "monthly_revenue": RNG.gamma(2.0, 30.0, N).round(2),
            "region_code": "EMEA",  # constant column — no information
        }
    )

    # --- Inject realistic quality problems -------------------------------

    # 1) Missing values: ~8% of age, ~15% of monthly_revenue.
    df.loc[RNG.choice(N, int(N * 0.08), replace=False), "age"] = np.nan
    df.loc[RNG.choice(N, int(N * 0.15), replace=False), "monthly_revenue"] = np.nan

    # 2) Out-of-range / impossible values.
    df.loc[RNG.choice(N, 5, replace=False), "age"] = RNG.integers(150, 200, 5)  # impossible ages
    df.loc[RNG.choice(N, 8, replace=False), "monthly_revenue"] *= -1            # negative revenue

    # 3) Outliers in revenue (a few whales).
    df.loc[RNG.choice(N, 6, replace=False), "monthly_revenue"] = RNG.uniform(5000, 9000, 6)

    # 4) Invalid category value not in the allowed set.
    df.loc[RNG.choice(N, 4, replace=False), "status"] = "unknown"

    # 5) Schema drift: store customer_id as float (e.g. after a bad join).
    df["customer_id"] = df["customer_id"].astype(float)

    # 6) Duplicate rows (a botched append) + a primary-key collision.
    dupes = df.sample(12, random_state=1)
    df = pd.concat([df, dupes], ignore_index=True)
    df.loc[df.index[-1], "customer_id"] = df.loc[0, "customer_id"]  # PK collision

    return df


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df):,} rows x {df.shape[1]} cols -> {OUT}")


if __name__ == "__main__":
    main()
