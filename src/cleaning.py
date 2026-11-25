"""
Deterministic, reusable data cleaning and standardisation functions.

Documented business rules / assumptions
---------------------------------------
A1  Product names are standardised by stripping whitespace and converting to
    title case ("LAPTOP", "laptop" -> "Laptop").
A2  Dates are parsed ONLY with these explicit formats, in this order:
        %Y-%m-%d  (ISO, e.g. 2026-01-05)
        %d/%m/%Y  (day-first, e.g. 06/01/2026 -> 6 January 2026)
        %d-%m-%Y  (day-first, e.g. 09-01-2026 -> 9 January 2026)
    Day-first is assumed because (a) the company is Zimbabwean, where DD/MM/YYYY
    is standard, (b) the brief states the data covers January 2026, and (c) the
    resulting dates run in strict sequence with the Transaction_IDs. The
    alternative month-first reading would place these sales in June, September,
    December etc., which contradicts the brief. A value that matches no format
    is rejected, never guessed.
A3  Missing Unit_Price values are NOT imputed (no zero-fill, no averages):
    revenue cannot be established without the invoiced price, so the record is
    rejected and sent for manual review.
A4  Negative quantities may be returns/reversals, but there is no link to an
    original sale, so they cannot be netted safely. They are rejected from the
    sales dataset and sent for manual review (not silently deleted).
A5  Zero quantities represent no sale; they are rejected for review
    (possible cancelled or incomplete transactions).
A6  Discounts must lie in [0, 100]. Values outside the range are rejected.
A7  Original values are preserved: the raw DataFrame is never modified and the
    cleaned output keeps Original_Product and Original_Date columns.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .validation import EXPECTED_PRODUCT_CATEGORY, DISCOUNT_MIN, DISCOUNT_MAX

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
TEXT_COLUMNS = ["Transaction_ID", "Product", "Category", "Salesperson", "City", "Payment_Method"]
NUMERIC_COLUMNS = ["Quantity", "Unit_Price", "Unit_Cost", "Discount_Percent"]


@dataclass
class CleaningResult:
    """Container for the outputs of ``clean_sales_data``."""
    accepted: pd.DataFrame
    rejected: pd.DataFrame
    summary: pd.DataFrame


# ---------------------------------------------------------------------------
# Individual, reusable cleaning functions
# ---------------------------------------------------------------------------
def standardise_product_names(products):
    """Strip whitespace and convert product names to title case (rule A1)."""
    return products.astype("string").str.strip().str.title()


def standardise_text_columns(df, columns=None):
    """Strip leading/trailing whitespace from text columns. Returns a copy."""
    result = df.copy()
    for column in columns or TEXT_COLUMNS:
        result[column] = result[column].astype("string").str.strip()
    return result


def parse_dates(date_values, formats=DATE_FORMATS):
    """Convert mixed-format date strings to datetime using explicit formats only
    (rule A2). Unparseable values become NaT so they can be rejected.

    Raises ``ValueError`` if any value matches more than one format, which
    would make it ambiguous.
    """
    text = pd.Series(date_values).astype("string").str.strip()
    attempts = [pd.to_datetime(text, format=fmt, errors="coerce") for fmt in formats]
    match_count = sum(a.notna().astype(int) for a in attempts)
    if (match_count > 1).any():
        raise ValueError(f"Ambiguous dates matched multiple formats: {text[match_count > 1].tolist()}")
    parsed = attempts[0]
    for attempt in attempts[1:]:
        parsed = parsed.fillna(attempt)
    return parsed


def coerce_numeric_types(df):
    """Convert numeric fields to numeric dtypes. Invalid entries become NaN so
    they can be flagged (never silently converted to 0). Returns a copy."""
    result = df.copy()
    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    # Quantity is a count: use nullable integer when values are whole numbers
    quantity = result["Quantity"]
    if (quantity.dropna() % 1 == 0).all():
        result["Quantity"] = quantity.astype("Int64")
    result["Unit_Price"] = result["Unit_Price"].astype("float64")
    result["Unit_Cost"] = result["Unit_Cost"].astype("float64")
    result["Discount_Percent"] = result["Discount_Percent"].astype("float64")
    return result


def flag_records_for_review(df):
    """Return a Series of review reasons ('' means the record is acceptable).

    Implements rules A2-A6. Several reasons are joined with '; '.
    """
    rules = [
        (df["Date"].isna(), "Invalid or unparseable date"),
        (df["Quantity"].isna(), "Missing or non-numeric quantity"),
        (df["Quantity"] < 0, "Negative quantity - possible return/reversal; requires verification"),
        (df["Quantity"] == 0, "Zero quantity - no goods sold"),
        (df["Unit_Price"].isna(), "Missing unit price - not imputed"),
        (df["Unit_Price"] <= 0, "Non-positive unit price"),
        (df["Unit_Cost"].isna() | (df["Unit_Cost"] < 0), "Missing or negative unit cost"),
        (df["Discount_Percent"].isna()
         | (df["Discount_Percent"] < DISCOUNT_MIN)
         | (df["Discount_Percent"] > DISCOUNT_MAX), "Discount missing or outside 0-100%"),
        (~df["Product"].isin(list(EXPECTED_PRODUCT_CATEGORY)), "Unknown product"),
        (df["Transaction_ID"].duplicated(keep="first"), "Duplicate Transaction_ID"),
    ]
    collected = [[] for _ in range(len(df))]
    for condition, reason in rules:
        flags = condition.fillna(False).astype(bool).to_numpy()
        for position in np.flatnonzero(flags):
            collected[position].append(reason)
    return pd.Series(["; ".join(r) for r in collected], index=df.index, dtype="object")


def verify_no_new_duplicates(raw_df, cleaned_df):
    """Confirm cleaning has not introduced duplicate Transaction_IDs and that
    no record has been lost or created."""
    raw_ids = raw_df["Transaction_ID"].astype("string").str.strip()
    if cleaned_df["Transaction_ID"].duplicated().sum() > raw_ids.duplicated().sum():
        raise ValueError("Cleaning introduced duplicate Transaction_IDs.")
    if cleaned_df.duplicated(subset=["Transaction_ID", "Date", "Product", "Quantity"]).sum() > \
            raw_df.duplicated(subset=["Transaction_ID", "Date", "Product", "Quantity"]).sum():
        raise ValueError("Cleaning introduced duplicate records.")
    if len(cleaned_df) != len(raw_df):
        raise ValueError("Cleaning changed the number of records before accept/reject split.")
    return True


# ---------------------------------------------------------------------------
# Orchestrating cleaning function
# ---------------------------------------------------------------------------
def clean_sales_data(raw_df):
    """Clean the raw sales DataFrame and split it into accepted and rejected
    records. The raw DataFrame is not modified.

    Returns a ``CleaningResult``.
    """
    working = raw_df.copy()

    # Preserve original values for the audit trail (rule A7)
    working["Original_Product"] = raw_df["Product"].astype("string")
    working["Original_Date"] = raw_df["Date"].astype("string")
    working["Original_Quantity"] = raw_df["Quantity"]
    working["Original_Unit_Price"] = raw_df["Unit_Price"]

    working = standardise_text_columns(working)
    working["Product"] = standardise_product_names(working["Product"])
    working["Date"] = parse_dates(working["Date"])
    working = coerce_numeric_types(working)

    verify_no_new_duplicates(raw_df, working)

    working["Review_Reason"] = flag_records_for_review(working)
    working["Product_Name_Changed"] = working["Product"] != working["Original_Product"]
    working["Date_Reformatted"] = working["Date"].dt.strftime("%Y-%m-%d") != working["Original_Date"]
    working["Date_Reformatted"] = working["Date_Reformatted"].fillna(False).astype(bool)

    is_rejected = working["Review_Reason"] != ""
    accepted = working.loc[~is_rejected].drop(columns=["Review_Reason"]).reset_index(drop=True)
    rejected = working.loc[is_rejected].reset_index(drop=True)
    rejected["Record_Status"] = "Rejected - manual review required"

    accepted = accepted.drop(columns=["Original_Quantity", "Original_Unit_Price"])
    accepted["Quantity"] = accepted["Quantity"].astype("int64")

    summary = pd.DataFrame([
        ("Raw records", len(raw_df)),
        ("Accepted records", len(accepted)),
        ("Rejected records (manual review)", len(rejected)),
        ("Product names standardised", int(working["Product_Name_Changed"].sum())),
        ("Dates converted from non-ISO formats", int(working["Date_Reformatted"].sum())),
        ("Unparseable dates", int(working["Date"].isna().sum())),
        ("Missing unit prices (not imputed)", int(working["Unit_Price"].isna().sum())),
        ("Negative quantities", int((working["Quantity"] < 0).sum())),
        ("Zero quantities", int((working["Quantity"] == 0).sum())),
        ("Duplicate Transaction_IDs after cleaning", int(working["Transaction_ID"].duplicated().sum())),
        ("Records reconciled (accepted + rejected = raw)", bool(len(accepted) + len(rejected) == len(raw_df))),
    ], columns=["Metric", "Value"])

    return CleaningResult(accepted=accepted, rejected=rejected, summary=summary)


def update_resolution_status(quality_report, cleaning_result):
    """Set the Resolution_Status of each data quality issue according to the
    cleaning outcome. Returns a new DataFrame."""
    report = quality_report.copy()
    rejected_ids = set(cleaning_result.rejected["Transaction_ID"])
    accepted_ids = set(cleaning_result.accepted["Transaction_ID"])
    status = np.select(
        [report["Transaction_ID"].isin(rejected_ids),
         report["Transaction_ID"].isin(accepted_ids),
         report["Transaction_ID"] == "(column-level)"],
        ["Unresolved - record quarantined for manual review",
         "Resolved - standardised during cleaning",
         "Resolved - dtype corrected during cleaning"],
        default="Open",
    )
    report["Resolution_Status"] = status
    return report
