"""
Financial transformation, sales aggregation, time-series analysis,
segmentation, multi-DataFrame operations and business-intelligence helpers.

Metric definitions (used consistently everywhere)
-------------------------------------------------
Gross_Revenue       = Quantity * Unit_Price
Discount_Amount     = Gross_Revenue * (Discount_Percent / 100)
Net_Revenue         = Gross_Revenue - Discount_Amount
Total_Cost          = Quantity * Unit_Cost
Gross_Profit        = Net_Revenue - Total_Cost
Gross_Profit_Margin = Gross_Profit / Net_Revenue * 100   (NaN if Net_Revenue == 0)

"Revenue" in rankings always means Net_Revenue (after discounts).
Overall / group margins are ALWAYS total Gross_Profit / total Net_Revenue,
never an average of individual transaction margins.
Average transaction value (ATV) = total Net_Revenue / number of valid transactions.
Ranks use method="min": tied values share the best rank (1, 1, 3 ...).
Gross profit is not net profit: operating expenses are not in the dataset.
"""

import numpy as np
import pandas as pd

from .validation import DataValidationError

FINANCIAL_TOLERANCE = 1e-6
SUM_COLUMNS = ["Quantity", "Gross_Revenue", "Discount_Amount", "Net_Revenue", "Total_Cost", "Gross_Profit"]


# ---------------------------------------------------------------------------
# Stage 4: financial transformation
# ---------------------------------------------------------------------------
def safe_margin(gross_profit, net_revenue):
    """Margin in percent; returns NaN where net revenue is zero (no division by zero)."""
    gross_profit = np.asarray(gross_profit, dtype="float64")
    net_revenue = np.asarray(net_revenue, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        margin = np.where(net_revenue != 0, gross_profit / net_revenue * 100, np.nan)
    return margin if margin.ndim else float(margin)


def add_financial_columns(df):
    """Add the six calculated financial columns using vectorised operations.
    Returns a new DataFrame; the input is not modified."""
    result = df.copy()
    result["Gross_Revenue"] = result["Quantity"] * result["Unit_Price"]
    result["Discount_Amount"] = result["Gross_Revenue"] * (result["Discount_Percent"] / 100)
    result["Net_Revenue"] = result["Gross_Revenue"] - result["Discount_Amount"]
    result["Total_Cost"] = result["Quantity"] * result["Unit_Cost"]
    result["Gross_Profit"] = result["Net_Revenue"] - result["Total_Cost"]
    result["Gross_Profit_Margin"] = safe_margin(result["Gross_Profit"], result["Net_Revenue"])
    result["Is_Loss_Making"] = result["Gross_Profit"] < 0
    return result


def verify_financial_calculations(df, tolerance=FINANCIAL_TOLERANCE):
    """Independently re-check every financial column, row by row, using
    plain Python arithmetic (not the vectorised formulas), within a tolerance.
    Raises ``DataValidationError`` on any mismatch."""
    problems = []
    for row in df.itertuples(index=False):
        gross = float(row.Quantity) * float(row.Unit_Price)
        discount = gross * float(row.Discount_Percent) / 100.0
        net = gross - discount
        cost = float(row.Quantity) * float(row.Unit_Cost)
        profit = net - cost
        checks = {
            "Gross_Revenue": (row.Gross_Revenue, gross),
            "Discount_Amount": (row.Discount_Amount, discount),
            "Net_Revenue": (row.Net_Revenue, net),
            "Total_Cost": (row.Total_Cost, cost),
            "Gross_Profit": (row.Gross_Profit, profit),
        }
        for name, (actual, expected) in checks.items():
            if not np.isclose(actual, expected, atol=tolerance):
                problems.append(f"{row.Transaction_ID} {name}: {actual} != {expected}")
        if net != 0 and not np.isclose(row.Gross_Profit_Margin, profit / net * 100, atol=tolerance):
            problems.append(f"{row.Transaction_ID} Gross_Profit_Margin mismatch")
        if not (0 <= discount <= gross + tolerance):
            problems.append(f"{row.Transaction_ID} discount amount outside 0..gross revenue")
    if problems:
        raise DataValidationError("Financial verification failed: " + "; ".join(problems))
    return True


def financial_summary(df):
    """Company-level financial KPIs as a one-column DataFrame."""
    totals = df[SUM_COLUMNS].sum()
    transactions = len(df)
    summary = {
        "Valid_Transactions": transactions,
        "Units_Sold": int(totals["Quantity"]),
        "Gross_Revenue": totals["Gross_Revenue"],
        "Discount_Amount": totals["Discount_Amount"],
        "Net_Revenue": totals["Net_Revenue"],
        "Total_Cost": totals["Total_Cost"],
        "Gross_Profit": totals["Gross_Profit"],
        "Overall_Gross_Profit_Margin_Pct": safe_margin(totals["Gross_Profit"], totals["Net_Revenue"]),
        "Average_Transaction_Value": totals["Net_Revenue"] / transactions if transactions else np.nan,
        "Effective_Discount_Rate_Pct": safe_margin(totals["Discount_Amount"], totals["Gross_Revenue"]),
        "Loss_Making_Transactions": int((df["Gross_Profit"] < 0).sum()),
    }
    return pd.DataFrame({"Metric": list(summary), "Value": list(summary.values())})


# ---------------------------------------------------------------------------
# Stage 5: aggregation and performance analysis
# ---------------------------------------------------------------------------
def group_performance(df, by):
    """Aggregate performance for one or more grouping columns.

    Returns transactions, units, revenue, cost, profit, margin (total-based),
    revenue share and a revenue rank (method='min').
    """
    grouped = (
        df.groupby(by, observed=True)
        .agg(
            Transactions=("Transaction_ID", "count"),
            Units_Sold=("Quantity", "sum"),
            Gross_Revenue=("Gross_Revenue", "sum"),
            Discount_Amount=("Discount_Amount", "sum"),
            Net_Revenue=("Net_Revenue", "sum"),
            Total_Cost=("Total_Cost", "sum"),
            Gross_Profit=("Gross_Profit", "sum"),
            Avg_Discount_Pct=("Discount_Percent", "mean"),
        )
        .reset_index()
    )
    grouped["Gross_Profit_Margin_Pct"] = safe_margin(grouped["Gross_Profit"], grouped["Net_Revenue"])
    grouped["Revenue_Share_Pct"] = grouped["Net_Revenue"] / grouped["Net_Revenue"].sum() * 100
    grouped["Profit_Share_Pct"] = grouped["Gross_Profit"] / grouped["Gross_Profit"].sum() * 100
    grouped["Avg_Transaction_Value"] = grouped["Net_Revenue"] / grouped["Transactions"]
    grouped["Revenue_Rank"] = grouped["Net_Revenue"].rank(ascending=False, method="min").astype(int)
    grouped["Profit_Rank"] = grouped["Gross_Profit"].rank(ascending=False, method="min").astype(int)
    return grouped.sort_values("Net_Revenue", ascending=False).reset_index(drop=True)


def reconcile_totals(grouped, transactions, columns=("Net_Revenue", "Gross_Profit"),
                     tolerance=FINANCIAL_TOLERANCE):
    """Check that grouped totals equal transaction-level totals."""
    for column in columns:
        if not np.isclose(grouped[column].sum(), transactions[column].sum(), atol=tolerance):
            raise DataValidationError(
                f"Reconciliation failed for {column}: grouped={grouped[column].sum()} "
                f"vs transactions={transactions[column].sum()}"
            )
    return True


def city_performance(df, operating_cities=None):
    """City performance. Cities with no records (e.g. Masvingo) are listed with
    NaN metrics and a 'No records in sample' note - NOT as zero sales."""
    result = group_performance(df, "City")
    result["Data_Note"] = "Records available"
    if operating_cities:
        missing = [c for c in operating_cities if c not in set(result["City"])]
        if missing:
            placeholder = pd.DataFrame({"City": missing, "Data_Note": "No records in sample - activity unknown"})
            result = pd.concat([result, placeholder], ignore_index=True)
    return result


def below_average_salespeople(salesperson_df, metric="Net_Revenue"):
    """Salespeople whose metric is below the average across salespeople."""
    average = salesperson_df[metric].mean()
    return salesperson_df.query(f"{metric} < @average").assign(Average=average)


def below_average_margin_products(product_df, overall_margin):
    """Products whose (total-based) margin is below the overall company margin."""
    return product_df[product_df["Gross_Profit_Margin_Pct"] < overall_margin]


# ---------------------------------------------------------------------------
# Stage 6: time-series analysis
# ---------------------------------------------------------------------------
def add_date_parts(df):
    result = df.copy()
    result["Day"] = result["Date"].dt.day
    result["Month"] = result["Date"].dt.month
    result["Year"] = result["Date"].dt.year
    result["Weekday"] = result["Date"].dt.day_name()
    return result


def daily_revenue(df, start=None, end=None):
    """Daily revenue on a complete calendar index.

    Dates with no *valid* transactions keep NaN revenue (unknown, not
    confirmed zero) and a transaction count of 0. Cumulative revenue and the
    rolling averages are computed after sorting chronologically.
    """
    daily = (
        df.sort_values("Date")
        .groupby("Date")
        .agg(Net_Revenue=("Net_Revenue", "sum"), Gross_Profit=("Gross_Profit", "sum"),
             Transactions=("Transaction_ID", "count"))
    )
    start = pd.Timestamp(start) if start is not None else daily.index.min()
    end = pd.Timestamp(end) if end is not None else daily.index.max()
    calendar = pd.date_range(start, end, freq="D", name="Date")
    full = daily.reindex(calendar)
    full["Transactions"] = full["Transactions"].fillna(0).astype(int)
    full["Has_Valid_Transactions"] = full["Transactions"] > 0
    # Cumulative revenue carries forward over days with no data
    full["Cumulative_Net_Revenue"] = full["Net_Revenue"].cumsum().ffill()
    # Transaction-day window: last 3 days that actually have transactions
    tx_days = full.loc[full["Has_Valid_Transactions"], "Net_Revenue"]
    full["Rolling_3_Transaction_Days"] = tx_days.rolling(3, min_periods=3).mean()
    # Calendar window: last 3 calendar days, averaging only days with data
    full["Rolling_3_Calendar_Days"] = full["Net_Revenue"].rolling("3D", min_periods=1).mean()
    return full.reset_index()


def compare_periods(df, periods):
    """Compare revenue between named reporting periods, normalised by length.

    ``periods`` maps a label to a (start, end) tuple of inclusive dates.
    """
    rows = []
    for label, (start, end) in periods.items():
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        subset = df[(df["Date"] >= start) & (df["Date"] <= end)]
        calendar_days = (end - start).days + 1
        trading_days = subset["Date"].nunique()
        revenue = subset["Net_Revenue"].sum()
        rows.append({
            "Period": label, "Start": start.date(), "End": end.date(),
            "Calendar_Days": calendar_days, "Days_With_Valid_Transactions": trading_days,
            "Transactions": len(subset), "Net_Revenue": revenue,
            "Gross_Profit": subset["Gross_Profit"].sum(),
            "Revenue_Per_Calendar_Day": revenue / calendar_days,
            "Revenue_Per_Transaction_Day": revenue / trading_days if trading_days else np.nan,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stage 7: segmentation
# ---------------------------------------------------------------------------
def segment_transactions(df):
    """Classify every transaction as Low / Medium / High value.

    Thresholds are the 33.3rd and 66.7th percentiles (tertiles) of net revenue
    of the valid transactions, so roughly a third of transactions fall in each
    band. Conditions are mutually exclusive and exhaustive:
        Low    : Net_Revenue <  P33
        Medium : P33 <= Net_Revenue < P67
        High   : Net_Revenue >= P67
    Returns (DataFrame, thresholds_dict).
    """
    result = df.copy()
    low_cut, high_cut = result["Net_Revenue"].quantile([1 / 3, 2 / 3]).tolist()
    conditions = [
        result["Net_Revenue"] < low_cut,
        (result["Net_Revenue"] >= low_cut) & (result["Net_Revenue"] < high_cut),
        result["Net_Revenue"] >= high_cut,
    ]
    result["Value_Segment"] = np.select(conditions, ["Low", "Medium", "High"], default="Unclassified")
    if (result["Value_Segment"] == "Unclassified").any():
        raise DataValidationError("Some transactions could not be classified.")
    return result, {"Low_below": low_cut, "High_from": high_cut}


def classify_performance(group_df, revenue_col="Net_Revenue", margin_col="Gross_Profit_Margin_Pct",
                         overall_margin=None):
    """Two-dimensional classification (revenue vs margin):
        Star            - revenue >= average AND margin >= overall margin
        Volume Driver   - revenue >= average AND margin <  overall margin
        Margin Niche    - revenue <  average AND margin >= overall margin
        Underperformer  - revenue <  average AND margin <  overall margin
    """
    result = group_df.copy()
    avg_revenue = result[revenue_col].mean()
    if overall_margin is None:
        overall_margin = safe_margin(result["Gross_Profit"].sum(), result[revenue_col].sum())
    high_rev = result[revenue_col] >= avg_revenue
    high_margin = result[margin_col] >= overall_margin
    result["Performance_Class"] = np.select(
        [high_rev & high_margin, high_rev & ~high_margin, ~high_rev & high_margin],
        ["Star", "Volume Driver", "Margin Niche"], default="Underperformer",
    )
    return result


def flag_high_discounts(df, threshold=10):
    """Flag transactions whose discount is at or above ``threshold`` percent
    (10% is the highest discount tier observed in the sample)."""
    result = df.copy()
    result["High_Discount"] = result["Discount_Percent"] >= threshold
    return result


# ---------------------------------------------------------------------------
# Stage 8: multi-DataFrame operations
# ---------------------------------------------------------------------------
PRODUCT_CODE_PATTERN = r"^ZT-[A-Z]{3}-\d{3}$"


def prepare_product_reference(reference_df):
    """Validate product codes and standardise names in the reference data."""
    ref = reference_df.copy()
    ref["Product_Name"] = ref["Product_Name"].astype("string").str.strip().str.title()
    ref["Product_Code"] = ref["Product_Code"].astype("string").str.strip()
    invalid_codes = ref.loc[~ref["Product_Code"].str.match(PRODUCT_CODE_PATTERN), "Product_Code"]
    if not invalid_codes.empty:
        raise DataValidationError(f"Invalid product codes: {invalid_codes.tolist()}")
    if ref["Product_Code"].duplicated().any():
        raise DataValidationError("Duplicate product codes in reference data.")
    if ref["Product_Name"].duplicated().any():
        raise DataValidationError("Duplicate product names in reference data (merge key not unique).")
    return ref


def merge_sales_with_reference(sales_df, reference_df, how="left"):
    """Merge sales (many) to reference (one) on standardised product name,
    enforcing a many-to-one relationship. Verifies that the row count and
    revenue are unchanged for a left join."""
    merged = sales_df.merge(
        reference_df, left_on="Product", right_on="Product_Name",
        how=how, validate="many_to_one", indicator=True,
    )
    if merged["Transaction_ID"].duplicated().any():
        raise DataValidationError("Merge introduced duplicate transactions.")
    if how == "left":
        if len(merged) != len(sales_df):
            raise DataValidationError("Left merge changed the number of sales rows.")
        if not np.isclose(merged["Net_Revenue"].sum(), sales_df["Net_Revenue"].sum()):
            raise DataValidationError("Left merge changed total net revenue.")
    return merged


def unmatched_records(sales_df, reference_df):
    """Outer join to expose records on either side with no match."""
    outer = sales_df[["Transaction_ID", "Product"]].merge(
        reference_df[["Product_Code", "Product_Name"]],
        left_on="Product", right_on="Product_Name", how="outer", indicator=True,
    )
    return outer[outer["_merge"] != "both"]


def revenue_pivot(df, index="City", columns="Category", values="Net_Revenue"):
    """City x Category (or other) pivot with totals. Empty cells are 0 here
    because they represent *valid observed* combinations with no sales in the
    sample period, not missing data."""
    return pd.pivot_table(df, index=index, columns=columns, values=values,
                          aggfunc="sum", fill_value=0, margins=True, margins_name="Total")
