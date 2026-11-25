"""
Automated tests for the ZimTech sales pipeline.

Run from the repository root:   python -m pytest -v

Expected values are hand-calculated constants (not recomputed with the
production formulas) so that a faulty formula cannot pass its own test.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src import analytics, cleaning, validation
from src.pipeline import run_pipeline
from src.source_data import get_product_reference, get_sales_data, sales_data


# ---------------------------------------------------------------------------
# Fixtures: small datasets with known answers
# ---------------------------------------------------------------------------
def make_record(**overrides):
    record = {
        "Transaction_ID": "T1", "Date": "2026-01-05", "Product": "Laptop",
        "Category": "Computers", "Quantity": 2, "Unit_Price": 100.0, "Unit_Cost": 60.0,
        "Salesperson": "John", "City": "Harare", "Payment_Method": "Cash",
        "Discount_Percent": 10,
    }
    record.update(overrides)
    return record


def records_to_dict(records):
    return {key: [r[key] for r in records] for key in records[0]}


@pytest.fixture
def known_dataset():
    """Two valid records with hand-calculated results.

    T1: 2 x 100, 10% discount -> gross 200, discount 20, net 180,
        cost 120, profit 60, margin 33.3333%
    T2: 5 x 20,  0% discount  -> gross 100, discount 0, net 100,
        cost 50, profit 50, margin 50%
    Totals: net 280, profit 110, overall margin 39.2857% (NOT avg 41.67%)
    """
    return records_to_dict([
        make_record(),
        make_record(Transaction_ID="T2", Date="06/01/2026", Product="mouse",
                    Category="Accessories", Quantity=5, Unit_Price=20.0, Unit_Cost=10.0,
                    Discount_Percent=0, City="Gweru"),
    ])


def cleaned_financials(data_dict):
    raw = validation.build_dataframe(data_dict)
    result = cleaning.clean_sales_data(raw)
    return analytics.add_financial_columns(result.accepted), result


# ---------------------------------------------------------------------------
# 1. Mandatory columns / schema
# ---------------------------------------------------------------------------
def test_missing_mandatory_column_raises():
    data = get_sales_data()
    del data["Unit_Price"]
    df = pd.DataFrame(data)
    with pytest.raises(validation.SchemaValidationError, match="Unit_Price"):
        validation.validate_schema(df)


def test_valid_schema_passes_and_reports_types():
    report = validation.validate_schema(pd.DataFrame(get_sales_data()))
    assert report["Compatible"].all()
    assert set(validation.MANDATORY_COLUMNS) == set(report["Column"])


def test_inconsistent_list_lengths_raise():
    data = get_sales_data()
    data["Quantity"] = data["Quantity"][:-1]
    with pytest.raises(validation.SchemaValidationError, match="Inconsistent list lengths"):
        validation.build_dataframe(data)


def test_text_in_numeric_column_fails_schema():
    data = get_sales_data()
    data["Quantity"] = ["two"] + data["Quantity"][1:]
    with pytest.raises(validation.SchemaValidationError, match="Quantity"):
        validation.validate_schema(pd.DataFrame(data))


# ---------------------------------------------------------------------------
# 2. Unique transaction identifiers
# ---------------------------------------------------------------------------
def test_duplicate_transaction_ids_detected_and_rejected(known_dataset):
    data = copy.deepcopy(known_dataset)
    data["Transaction_ID"][1] = "T1"
    raw = validation.build_dataframe(data)
    issues, summary = validation.assess_data_quality(raw)
    assert summary.set_index("Rule").at["duplicate_transaction_id", "Violations"] == 2
    result = cleaning.clean_sales_data(raw)
    assert result.accepted["Transaction_ID"].is_unique
    assert "Duplicate Transaction_ID" in result.rejected["Review_Reason"].iloc[0]


def test_rule_can_report_no_violations():
    _, summary = validation.assess_data_quality(pd.DataFrame(get_sales_data()))
    row = summary.set_index("Rule").loc["duplicate_transaction_id"]
    assert row["Violations"] == 0 and row["Status"] == "PASS"


# ---------------------------------------------------------------------------
# 3-4. Valid quantities and unit prices
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("quantity", [-2, 0])
def test_non_positive_quantities_rejected(known_dataset, quantity):
    data = copy.deepcopy(known_dataset)
    data["Quantity"][0] = quantity
    _, result = cleaned_financials(data)
    assert "T1" in set(result.rejected["Transaction_ID"])
    assert "T1" not in set(result.accepted["Transaction_ID"])


def test_boundary_quantity_of_one_is_accepted(known_dataset):
    data = copy.deepcopy(known_dataset)
    data["Quantity"][0] = 1
    financial, result = cleaned_financials(data)
    assert len(result.accepted) == 2


def test_missing_price_is_rejected_not_zero_filled(known_dataset):
    data = copy.deepcopy(known_dataset)
    data["Unit_Price"][0] = None
    financial, result = cleaned_financials(data)
    assert list(result.rejected["Transaction_ID"]) == ["T1"]
    assert np.isnan(result.rejected.loc[0, "Unit_Price"])  # not replaced by 0
    assert (financial["Unit_Price"] > 0).all()


# ---------------------------------------------------------------------------
# 5. Discounts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("discount, accepted", [(0, True), (100, True), (-5, False), (150, False)])
def test_discount_boundaries(known_dataset, discount, accepted):
    data = copy.deepcopy(known_dataset)
    data["Discount_Percent"][0] = discount
    _, result = cleaned_financials(data)
    assert ("T1" in set(result.accepted["Transaction_ID"])) is accepted


def test_discount_amount_divides_percentage_by_100(known_dataset):
    financial, _ = cleaned_financials(known_dataset)
    t1 = financial.set_index("Transaction_ID").loc["T1"]
    assert t1["Discount_Amount"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 6-7. Revenue and gross profit calculations
# ---------------------------------------------------------------------------
def test_revenue_calculations_match_hand_calculation(known_dataset):
    financial, _ = cleaned_financials(known_dataset)
    t = financial.set_index("Transaction_ID")
    assert t.at["T1", "Gross_Revenue"] == pytest.approx(200.0)
    assert t.at["T1", "Net_Revenue"] == pytest.approx(180.0)
    assert t.at["T2", "Net_Revenue"] == pytest.approx(100.0)


def test_gross_profit_and_margin_match_hand_calculation(known_dataset):
    financial, _ = cleaned_financials(known_dataset)
    t = financial.set_index("Transaction_ID")
    assert t.at["T1", "Total_Cost"] == pytest.approx(120.0)
    assert t.at["T1", "Gross_Profit"] == pytest.approx(60.0)
    assert t.at["T1", "Gross_Profit_Margin"] == pytest.approx(33.333333, abs=1e-4)
    summary = analytics.financial_summary(financial).set_index("Metric")["Value"]
    # Overall margin = 110 / 280, not the average of 33.33% and 50%
    assert summary["Overall_Gross_Profit_Margin_Pct"] == pytest.approx(39.285714, abs=1e-4)
    assert summary["Average_Transaction_Value"] == pytest.approx(140.0)


def test_zero_net_revenue_gives_nan_margin_not_error(known_dataset):
    data = copy.deepcopy(known_dataset)
    data["Discount_Percent"][0] = 100   # net revenue becomes 0
    financial, _ = cleaned_financials(data)
    t1 = financial.set_index("Transaction_ID").loc["T1"]
    assert t1["Net_Revenue"] == 0
    assert np.isnan(t1["Gross_Profit_Margin"])
    assert bool(t1["Is_Loss_Making"]) is True


def test_financial_verification_detects_tampering(known_dataset):
    financial, _ = cleaned_financials(known_dataset)
    tampered = financial.copy()
    tampered.loc[0, "Net_Revenue"] += 1
    with pytest.raises(validation.DataValidationError):
        analytics.verify_financial_calculations(tampered)


# ---------------------------------------------------------------------------
# 8. Dates
# ---------------------------------------------------------------------------
def test_mixed_date_formats_parsed_day_first():
    parsed = cleaning.parse_dates(["2026-01-05", "06/01/2026", "09-01-2026"])
    assert list(parsed) == [pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06"),
                            pd.Timestamp("2026-01-09")]


def test_invalid_date_rejected(known_dataset):
    data = copy.deepcopy(known_dataset)
    data["Date"][0] = "2026-13-45"
    _, result = cleaned_financials(data)
    assert "Invalid or unparseable date" in result.rejected.loc[0, "Review_Reason"]


# ---------------------------------------------------------------------------
# 9. Merges
# ---------------------------------------------------------------------------
def test_left_merge_preserves_rows_and_revenue():
    results = run_pipeline(export=False)
    financial, reference = results["financial"], results["reference"]
    merged = analytics.merge_sales_with_reference(financial, reference, how="left")
    assert len(merged) == len(financial)
    assert merged["Net_Revenue"].sum() == pytest.approx(financial["Net_Revenue"].sum())
    assert (merged["_merge"] == "both").all()


def test_duplicate_reference_key_is_refused():
    reference = pd.DataFrame(get_product_reference())
    duplicated = pd.concat([reference, reference.iloc[[0]]], ignore_index=True)
    with pytest.raises(validation.DataValidationError):
        analytics.prepare_product_reference(duplicated)
    results = run_pipeline(export=False)
    raw_ref = duplicated.assign(Product_Name=duplicated["Product_Name"].str.strip().str.title())
    with pytest.raises(pd.errors.MergeError):
        analytics.merge_sales_with_reference(results["financial"], raw_ref)


# ---------------------------------------------------------------------------
# 10. Financial reconciliation and full pipeline
# ---------------------------------------------------------------------------
def test_grouped_totals_reconcile_with_transactions():
    results = run_pipeline(export=False)
    financial = results["financial"]
    for name, table in results["tables"].items():
        observed = table.dropna(subset=["Net_Revenue"])
        assert observed["Net_Revenue"].sum() == pytest.approx(financial["Net_Revenue"].sum()), name


def test_full_pipeline_known_totals(tmp_path):
    results = run_pipeline(output_dir=tmp_path)
    summary = results["analysis"]["sales_summary"].set_index("Metric")["Value"]
    assert summary["Valid_Transactions"] == 17
    assert summary["Net_Revenue"] == pytest.approx(13340.5)
    assert summary["Gross_Profit"] == pytest.approx(3255.5)
    assert len(results["cleaning"].accepted) + len(results["cleaning"].rejected) == 20
    assert (tmp_path / "cleaned_sales.csv").exists()
    assert sorted(results["cleaning"].rejected["Transaction_ID"]) == ["TX009", "TX012", "TX015"]


# ---------------------------------------------------------------------------
# Deliberately invalid record + source protection
# ---------------------------------------------------------------------------
def test_deliberately_invalid_record_is_identified():
    data = get_sales_data()
    invalid = {
        "Transaction_ID": "TX999", "Date": "31/02/2026", "Product": "Laptop",
        "Category": "Computers", "Quantity": -5, "Unit_Price": None, "Unit_Cost": 500,
        "Salesperson": "John", "City": "Harare", "Payment_Method": "Cash",
        "Discount_Percent": 150,
    }
    for key, value in invalid.items():
        data[key].append(value)
    results = run_pipeline(source_dict=data, export=False)
    rejected = results["cleaning"].rejected.set_index("Transaction_ID")
    assert "TX999" in rejected.index
    reason = rejected.at["TX999", "Review_Reason"]
    for expected in ["Invalid or unparseable date", "Negative quantity",
                     "Missing unit price", "Discount missing or outside"]:
        assert expected in reason
    assert "TX999" in set(results["quality_report"]["Transaction_ID"])
    # Valid totals unchanged by the invalid record
    assert results["financial"]["Net_Revenue"].sum() == pytest.approx(13340.5)


def test_source_dictionary_is_not_modified():
    before = copy.deepcopy(sales_data)
    run_pipeline(export=False)
    assert sales_data == before


def test_cleaned_output_passes_business_rules():
    results = run_pipeline(export=False)
    assert validation.validate_cleaned_dataset(results["cleaning"].accepted)
    bad = results["cleaning"].accepted.copy()
    bad.loc[0, "Quantity"] = -1
    with pytest.raises(validation.DataValidationError):
        validation.validate_cleaned_dataset(bad)
