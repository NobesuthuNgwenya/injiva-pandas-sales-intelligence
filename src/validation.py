"""
Structural (schema) validation, rule-based data quality assessment and
business-rule validation of the cleaned dataset.

Design principle: *structural* validation (are the columns there, are the
types usable?) is kept separate from *business-rule* validation (is a quantity
positive, is a discount between 0 and 100?).
"""

import copy

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------
# Every field is mandatory: each one is needed either for financial
# calculations (Quantity, Unit_Price, Unit_Cost, Discount_Percent), for
# identifying/auditing a transaction (Transaction_ID, Date) or for the required
# performance analyses (Product, Category, Salesperson, City, Payment_Method).
MANDATORY_COLUMNS = [
    "Transaction_ID", "Date", "Product", "Category", "Quantity",
    "Unit_Price", "Unit_Cost", "Salesperson", "City",
    "Payment_Method", "Discount_Percent",
]

# Logical (business) type expected for each field after cleaning.
EXPECTED_SCHEMA = {
    "Transaction_ID": "string",
    "Date": "datetime",
    "Product": "string",
    "Category": "string",
    "Quantity": "integer",
    "Unit_Price": "numeric",
    "Unit_Cost": "numeric",
    "Salesperson": "string",
    "City": "string",
    "Payment_Method": "string",
    "Discount_Percent": "numeric",
}

# Business reference values
VALID_CATEGORIES = ["Computers", "Mobile", "Accessories", "Office Equipment"]
EXPECTED_PRODUCT_CATEGORY = {
    "Laptop": "Computers",
    "Monitor": "Computers",
    "Smartphone": "Mobile",
    "Keyboard": "Accessories",
    "Mouse": "Accessories",
    "Printer": "Office Equipment",
}
VALID_PAYMENT_METHODS = ["Cash", "EcoCash", "Bank Transfer"]
DISCOUNT_MIN, DISCOUNT_MAX = 0, 100
# Discounts above this level are outside normal practice in the sample
# (observed tiers are 0%, 5% and 10%) and are flagged as suspicious.
SUSPICIOUS_DISCOUNT_THRESHOLD = 15
ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class SchemaValidationError(Exception):
    """Raised when a dataset fails structural (schema) validation."""


class DataValidationError(Exception):
    """Raised when a dataset fails business-rule validation."""


# ---------------------------------------------------------------------------
# Stage 1: construction and structural validation
# ---------------------------------------------------------------------------
def check_list_lengths(data_dict):
    """Verify that every list in a column-oriented dictionary has the same length.

    Returns the common length. Raises ``SchemaValidationError`` otherwise.
    """
    if not isinstance(data_dict, dict) or not data_dict:
        raise SchemaValidationError("Source data must be a non-empty dictionary.")
    lengths = {column: len(values) for column, values in data_dict.items()}
    if len(set(lengths.values())) != 1:
        raise SchemaValidationError(
            f"Inconsistent list lengths in source dictionary: {lengths}"
        )
    return next(iter(lengths.values()))


def build_dataframe(data_dict):
    """Convert a column-oriented dictionary into a DataFrame without
    modifying the original dictionary."""
    check_list_lengths(data_dict)
    return pd.DataFrame(copy.deepcopy(data_dict))


def _type_check(series, expected):
    """Return (compatible: bool, note: str) for a column versus its logical type."""
    if expected == "string":
        ok = pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
        if ok:
            non_null = series.dropna()
            ok = bool(non_null.map(lambda v: isinstance(v, str)).all())
        return ok, "" if ok else "contains non-text values"
    if expected == "integer":
        if pd.api.types.is_integer_dtype(series):
            return True, ""
        if pd.api.types.is_float_dtype(series):
            whole = (series.dropna() % 1 == 0).all()
            return bool(whole), "float storage; values are whole numbers" if whole else "non-integer values"
        return False, "non-numeric dtype"
    if expected == "numeric":
        ok = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
        note = ""
        if ok and series.isna().any():
            note = "numeric but contains missing values"
        return ok, note if ok else "non-numeric dtype"
    if expected == "datetime":
        if pd.api.types.is_datetime64_any_dtype(series):
            return True, ""
        if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
            return True, "stored as text - conversion to datetime required"
        return False, "not convertible to datetime"
    raise ValueError(f"Unknown expected type '{expected}'")


def validate_schema(df, mandatory_columns=None, expected_schema=None):
    """Reusable structural validation.

    * Raises ``SchemaValidationError`` if mandatory columns are missing
      (missing *columns* are a structural failure, unlike missing *values*).
    * Raises ``SchemaValidationError`` if a column's dtype cannot represent its
      logical type (e.g. text in Quantity).
    * Returns a DataFrame describing each column's expected and actual type.
    """
    mandatory_columns = MANDATORY_COLUMNS if mandatory_columns is None else mandatory_columns
    expected_schema = EXPECTED_SCHEMA if expected_schema is None else expected_schema

    if not isinstance(df, pd.DataFrame):
        raise SchemaValidationError("Input must be a pandas DataFrame.")

    missing = [c for c in mandatory_columns if c not in df.columns]
    if missing:
        raise SchemaValidationError(f"Missing mandatory column(s): {missing}")

    if df.empty:
        raise SchemaValidationError("DataFrame contains no records.")

    rows = []
    for column, expected in expected_schema.items():
        if column not in df.columns:
            continue
        compatible, note = _type_check(df[column], expected)
        rows.append({
            "Column": column,
            "Expected_Type": expected,
            "Actual_Dtype": str(df[column].dtype),
            "Compatible": compatible,
            "Missing_Values": int(df[column].isna().sum()),
            "Note": note,
        })
    report = pd.DataFrame(rows)

    incompatible = report.loc[~report["Compatible"], "Column"].tolist()
    if incompatible:
        raise SchemaValidationError(
            f"Column(s) with incompatible data types: {incompatible}\n{report}"
        )
    return report


# ---------------------------------------------------------------------------
# Stage 2: rule-based data quality assessment
# ---------------------------------------------------------------------------
def _issue(tx_id, column, value, issue, severity, action):
    return {
        "Transaction_ID": tx_id,
        "Column": column,
        "Original_Value": value,
        "Issue": issue,
        "Severity": severity,
        "Recommended_Action": action,
        "Resolution_Status": "Open",
    }


def _parse_known_formats(date_series):
    """Parse dates using only explicit, documented formats (see cleaning.py)."""
    text = date_series.astype("string").str.strip()
    parsed = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        parsed = parsed.fillna(pd.to_datetime(text, format=fmt, errors="coerce"))
    return parsed


def assess_data_quality(raw_df):
    """Run every data quality rule against the *raw* DataFrame.

    Returns ``(issues_df, rule_summary_df)``:
      * issues_df     - one row per detected issue (the Data Quality Report)
      * rule_summary  - one row per rule with its violation count, so a rule
                        can explicitly report that *no* violations were found.
    The input DataFrame is never modified.
    """
    df = raw_df.copy()
    ids = df["Transaction_ID"]
    issues, summary = [], []

    def record(rule, description, flagged):
        summary.append({
            "Rule": rule,
            "Description": description,
            "Violations": int(len(flagged)),
            "Status": "PASS" if len(flagged) == 0 else "FAIL",
        })

    # 1-2. Missing values (all columns except Unit_Price, handled by rule 7)
    flagged = []
    for column in df.columns.drop("Unit_Price"):
        for idx in df.index[df[column].isna()]:
            flagged.append(idx)
            issues.append(_issue(ids[idx], column, None, f"Missing value in {column}",
                                 "High", "Obtain value from source system"))
    record("missing_values", "Missing values in any column other than Unit_Price", flagged)

    # 3. Duplicate transaction identifiers (business key)
    dup_ids = df[df["Transaction_ID"].duplicated(keep=False)]
    for idx, row in dup_ids.iterrows():
        issues.append(_issue(row["Transaction_ID"], "Transaction_ID", row["Transaction_ID"],
                             "Duplicate transaction identifier", "Critical",
                             "Investigate; keep one authoritative record"))
    record("duplicate_transaction_id", "Transaction_ID must be unique", dup_ids.index)

    # 4. Completely duplicated records
    full_dups = df[df.duplicated(keep="first")]
    for idx, row in full_dups.iterrows():
        issues.append(_issue(row["Transaction_ID"], "ALL", "entire row",
                             "Completely duplicated record", "Critical",
                             "Remove duplicate after confirming with source"))
    record("duplicate_record", "No completely duplicated rows", full_dups.index)

    quantity = pd.to_numeric(df["Quantity"], errors="coerce")
    price = pd.to_numeric(df["Unit_Price"], errors="coerce")
    cost = pd.to_numeric(df["Unit_Cost"], errors="coerce")
    discount = pd.to_numeric(df["Discount_Percent"], errors="coerce")

    # 5. Negative quantities
    mask = quantity < 0
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Quantity", df.at[idx, "Quantity"],
                             "Negative quantity - possible return, reversal or entry error",
                             "High", "Quarantine for manual review; confirm with source "
                             "whether this is a return linked to an original sale"))
    record("negative_quantity", "Quantity must not be negative", df.index[mask])

    # 6. Zero quantities
    mask = quantity == 0
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Quantity", df.at[idx, "Quantity"],
                             "Zero quantity - no goods sold, record has no financial effect",
                             "Medium", "Quarantine for manual review (possible cancelled "
                             "or incomplete transaction)"))
    record("zero_quantity", "Quantity must not be zero", df.index[mask])

    # Non-numeric quantities
    mask = quantity.isna() & df["Quantity"].notna()
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Quantity", df.at[idx, "Quantity"],
                             "Non-numeric quantity", "High", "Correct at source"))
    record("non_numeric_quantity", "Quantity must be numeric", df.index[mask])

    # 7. Missing selling prices
    mask = df["Unit_Price"].isna()
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Unit_Price", None,
                             "Missing selling price - revenue cannot be determined",
                             "High", "Do not impute or zero-fill; quarantine and obtain the "
                             "invoiced price from the POS/finance system"))
    record("missing_unit_price", "Unit_Price must be present", df.index[mask])

    # 8. Invalid unit prices (non-numeric, zero/negative, or below unit cost)
    mask = (price.isna() & df["Unit_Price"].notna()) | (price <= 0)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Unit_Price", df.at[idx, "Unit_Price"],
                             "Invalid unit price (non-numeric or not positive)", "High",
                             "Correct at source"))
    record("invalid_unit_price", "Unit_Price must be numeric and > 0", df.index[mask])

    mask = price.notna() & cost.notna() & (price < cost)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Unit_Price", df.at[idx, "Unit_Price"],
                             "Selling price below unit cost", "Medium",
                             "Confirm pricing with Finance"))
    record("price_below_cost", "Unit_Price should not be below Unit_Cost", df.index[mask])

    # 9. Invalid unit costs
    mask = cost.isna() | (cost < 0)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Unit_Cost", df.at[idx, "Unit_Cost"],
                             "Missing, non-numeric or negative unit cost", "High",
                             "Obtain cost from inventory system"))
    record("invalid_unit_cost", "Unit_Cost must be numeric and >= 0", df.index[mask])

    # 10. Inconsistent product names
    product_text = df["Product"].astype("string")
    canonical = product_text.str.strip().str.title()
    mask = product_text.notna() & (product_text != canonical)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Product", df.at[idx, "Product"],
                             f"Inconsistent product naming (standard form: '{canonical[idx]}')",
                             "Low", "Standardise to title case"))
    record("inconsistent_product_name", "Product names must use standard title case", df.index[mask])

    # 11. Inconsistent / unknown categories
    category_text = df["Category"].astype("string")
    mask = category_text.notna() & ~category_text.isin(VALID_CATEGORIES)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Category", df.at[idx, "Category"],
                             "Category not in approved list", "Medium",
                             "Map to an approved category"))
    record("inconsistent_category", f"Category must be one of {VALID_CATEGORIES}", df.index[mask])

    # 12. Invalid dates and non-standard formats
    parsed = _parse_known_formats(df["Date"])
    mask = parsed.isna()
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Date", df.at[idx, "Date"],
                             "Invalid or unparseable date", "High",
                             "Quarantine; obtain correct date from source"))
    record("invalid_date", "Date must be a valid calendar date in a supported format", df.index[mask])

    date_text = df["Date"].astype("string").str.strip()
    mask = ~mask & ~date_text.str.match(ISO_DATE_PATTERN).fillna(False)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Date", df.at[idx, "Date"],
                             "Non-standard date format (day-first, not ISO 8601)", "Low",
                             "Parse with explicit day-first format and store as datetime"))
    record("non_iso_date_format", "Dates should be in ISO format YYYY-MM-DD", df.index[mask])

    # 13. Incorrect data types (column-level)
    type_flags = []
    if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
        type_flags.append("Date")
        issues.append(_issue("(column-level)", "Date", str(df["Date"].dtype),
                             "Date stored as text, not datetime", "Medium",
                             "Convert to datetime64 with explicit formats"))
    if pd.api.types.is_float_dtype(df["Unit_Price"]) and df["Unit_Price"].isna().any():
        type_flags.append("Unit_Price")
        issues.append(_issue("(column-level)", "Unit_Price", str(df["Unit_Price"].dtype),
                             "Integer prices coerced to float because of a missing value",
                             "Low", "Keep as float (currency); resolve missing value"))
    for column in ["Quantity", "Unit_Cost", "Discount_Percent"]:
        if not pd.api.types.is_numeric_dtype(df[column]):
            type_flags.append(column)
            issues.append(_issue("(column-level)", column, str(df[column].dtype),
                                 "Numeric field stored with non-numeric dtype", "High",
                                 "Convert with pd.to_numeric"))
    record("incorrect_dtype", "Columns must have dtypes matching their logical type", type_flags)

    # 14. Suspicious discount percentages
    mask = discount.isna() | (discount < DISCOUNT_MIN) | (discount > DISCOUNT_MAX)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Discount_Percent", df.at[idx, "Discount_Percent"],
                             "Discount missing or outside 0-100%", "High",
                             "Quarantine; confirm discount with Sales"))
    record("invalid_discount", "Discount_Percent must be between 0 and 100", df.index[mask])

    mask = ~mask & (discount > SUSPICIOUS_DISCOUNT_THRESHOLD)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Discount_Percent", df.at[idx, "Discount_Percent"],
                             f"Discount above {SUSPICIOUS_DISCOUNT_THRESHOLD}% policy level",
                             "Medium", "Confirm authorisation of discount"))
    record("suspicious_discount",
           f"Discount_Percent above {SUSPICIOUS_DISCOUNT_THRESHOLD}% is suspicious", df.index[mask])

    # 15. Unexpected product-category relationships
    expected_category = canonical.map(EXPECTED_PRODUCT_CATEGORY)
    mask = expected_category.isna() | (category_text != expected_category)
    for idx in df.index[mask]:
        issues.append(_issue(ids[idx], "Category", df.at[idx, "Category"],
                             f"Unexpected category for product '{df.at[idx, 'Product']}' "
                             f"(expected '{expected_category[idx]}')", "Medium",
                             "Verify product master data"))
    record("product_category_mismatch",
           "Each product must belong to its expected category", df.index[mask])

    issues_df = pd.DataFrame(issues, columns=[
        "Transaction_ID", "Column", "Original_Value", "Issue",
        "Severity", "Recommended_Action", "Resolution_Status",
    ])
    # Keep Original_Value as text so mixed types export cleanly to CSV
    issues_df["Original_Value"] = issues_df["Original_Value"].map(
        lambda v: "<missing>" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
    )
    return issues_df, pd.DataFrame(summary)


# ---------------------------------------------------------------------------
# Business-rule validation of the cleaned dataset
# ---------------------------------------------------------------------------
def find_business_rule_violations(df):
    """Return a list of human-readable violations for an *accepted* dataset."""
    violations = []
    missing = [c for c in MANDATORY_COLUMNS if c not in df.columns]
    if missing:
        return [f"Missing mandatory columns: {missing}"]
    if df["Transaction_ID"].duplicated().any():
        violations.append("Duplicate Transaction_IDs present")
    if df[MANDATORY_COLUMNS].isna().any().any():
        cols = df[MANDATORY_COLUMNS].columns[df[MANDATORY_COLUMNS].isna().any()].tolist()
        violations.append(f"Missing values in mandatory columns: {cols}")
    if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
        violations.append("Date column is not datetime")
    if (pd.to_numeric(df["Quantity"], errors="coerce") <= 0).any():
        violations.append("Non-positive quantities present")
    if (pd.to_numeric(df["Unit_Price"], errors="coerce") <= 0).any():
        violations.append("Non-positive unit prices present")
    if (pd.to_numeric(df["Unit_Cost"], errors="coerce") < 0).any():
        violations.append("Negative unit costs present")
    discount = pd.to_numeric(df["Discount_Percent"], errors="coerce")
    if ((discount < DISCOUNT_MIN) | (discount > DISCOUNT_MAX)).any():
        violations.append("Discounts outside 0-100% present")
    unknown_products = set(df["Product"]) - set(EXPECTED_PRODUCT_CATEGORY)
    if unknown_products:
        violations.append(f"Unknown/non-standard product names: {sorted(unknown_products)}")
    return violations


def validate_cleaned_dataset(df):
    """Raise ``DataValidationError`` if the accepted dataset breaks any rule."""
    violations = find_business_rule_violations(df)
    if violations:
        raise DataValidationError("Cleaned dataset failed validation: " + "; ".join(violations))
    return True
