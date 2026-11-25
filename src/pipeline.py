"""
End-to-end, reproducible sales data processing pipeline.

Run from the repository root:
    python -m src.pipeline

Each step is a separate function with one responsibility. Validation happens
before anything is exported.
"""

from pathlib import Path

import pandas as pd

from . import analytics, cleaning, validation
from .source_data import OPERATING_CITIES, get_product_reference, get_sales_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------
def construct_dataframe(source_dict=None):
    """Step 1 - build the raw DataFrame from (a copy of) the source dictionary."""
    source_dict = get_sales_data() if source_dict is None else source_dict
    return validation.build_dataframe(source_dict)


def validate_structure(raw_df):
    """Step 2 - structural schema validation (raises on failure)."""
    return validation.validate_schema(raw_df)


def assess_quality(raw_df):
    """Step 3 - rule-based data quality assessment."""
    return validation.assess_data_quality(raw_df)


def clean(raw_df):
    """Step 4 - cleaning, standardisation and accept/reject split."""
    result = cleaning.clean_sales_data(raw_df)
    validation.validate_cleaned_dataset(result.accepted)
    return result


def transform(accepted_df):
    """Step 5 - financial columns, verified independently."""
    financial = analytics.add_financial_columns(accepted_df)
    analytics.verify_financial_calculations(financial)
    return financial


def aggregate(financial_df):
    """Step 6 - grouped performance tables, each reconciled to the total."""
    tables = {
        "city_performance": analytics.city_performance(financial_df, OPERATING_CITIES),
        "product_performance": analytics.group_performance(financial_df, "Product"),
        "category_performance": analytics.group_performance(financial_df, "Category"),
        "salesperson_performance": analytics.group_performance(financial_df, "Salesperson"),
        "payment_method_performance": analytics.group_performance(financial_df, "Payment_Method"),
    }
    for name, table in tables.items():
        observed = table.dropna(subset=["Net_Revenue"])
        analytics.reconcile_totals(observed, financial_df)
    return tables


def analyse(financial_df, tables):
    """Step 7 - performance analysis outputs (summary, segmentation, time series)."""
    summary = analytics.financial_summary(financial_df)
    overall_margin = summary.set_index("Metric").at["Overall_Gross_Profit_Margin_Pct", "Value"]
    segmented, thresholds = analytics.segment_transactions(financial_df)
    product_classes = analytics.classify_performance(tables["product_performance"],
                                                     overall_margin=overall_margin)
    daily = analytics.daily_revenue(financial_df)
    return {
        "sales_summary": summary,
        "transaction_segments": segmented,
        "segment_thresholds": thresholds,
        "product_classification": product_classes,
        "daily_revenue": daily,
    }


def export_outputs(output_dir, raw_df, quality_report, rule_summary, cleaning_result,
                   financial_df, tables, analysis):
    """Step 8 - write CSV outputs (only called after all validation has passed)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rejected = cleaning_result.rejected.copy()
    rejected["Date"] = rejected["Date"].dt.strftime("%Y-%m-%d")

    files = {
        "raw_sales_original.csv": raw_df,
        "data_quality_report.csv": quality_report,
        "data_quality_rule_summary.csv": rule_summary,
        "cleaning_summary.csv": cleaning_result.summary,
        "cleaned_sales.csv": financial_df,
        "rejected_records.csv": rejected,
        "sales_summary.csv": analysis["sales_summary"],
        "city_performance.csv": tables["city_performance"],
        "product_performance.csv": analysis["product_classification"],
        "category_performance.csv": tables["category_performance"],
        "salesperson_performance.csv": tables["salesperson_performance"],
        "payment_method_performance.csv": tables["payment_method_performance"],
        "transaction_segments.csv": analysis["transaction_segments"][
            ["Transaction_ID", "Date", "Product", "Net_Revenue", "Gross_Profit_Margin", "Value_Segment"]],
        "daily_revenue.csv": analysis["daily_revenue"],
    }
    written = []
    for filename, frame in files.items():
        path = output_dir / filename
        frame.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.4f")
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_pipeline(source_dict=None, output_dir=DEFAULT_OUTPUT_DIR, export=True):
    """Run the full pipeline and return a dictionary with every intermediate result."""
    raw_df = construct_dataframe(source_dict)
    schema_report = validate_structure(raw_df)
    quality_report, rule_summary = assess_quality(raw_df)
    cleaning_result = clean(raw_df)
    quality_report = cleaning.update_resolution_status(quality_report, cleaning_result)
    financial_df = transform(cleaning_result.accepted)
    tables = aggregate(financial_df)
    analysis = analyse(financial_df, tables)

    written = []
    if export:
        written = export_outputs(output_dir, raw_df, quality_report, rule_summary,
                                 cleaning_result, financial_df, tables, analysis)
    return {
        "raw": raw_df,
        "schema_report": schema_report,
        "quality_report": quality_report,
        "rule_summary": rule_summary,
        "cleaning": cleaning_result,
        "financial": financial_df,
        "tables": tables,
        "analysis": analysis,
        "files": written,
        "reference": analytics.prepare_product_reference(pd.DataFrame(get_product_reference())),
    }


def main():
    results = run_pipeline()
    summary = results["analysis"]["sales_summary"]
    print("Pipeline completed successfully.\n")
    print(summary.to_string(index=False))
    print(f"\nAccepted: {len(results['cleaning'].accepted)}  "
          f"Rejected: {len(results['cleaning'].rejected)}")
    print("\nFiles written:")
    for path in results["files"]:
        print(f"  {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
