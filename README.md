# injiva-pandas-sales-intelligence

Sales data engineering and analytics pipeline for **ZimTech Retail Holdings**, a fictional company. The project was built for the INJIVA Digital Systems assessment `INJIVA-DS-DA-PANDAS-001`.

The pipeline:
1. converts the supplied Python dictionary into a validated Pandas DataFrame;
2. audits data quality with 18 repeatable rules;
3. cleans and standardises the records without losing original values;
4. calculates and independently verifies the financial metrics;
5. produces product, city, salesperson, time-series and segmentation analyses.

Results are exported as CSV files. There are no charts, as required by the brief.

## Project structure

```
injiva-pandas-sales-intelligence/
├── data/                       # generated CSV outputs (re-created by the pipeline)
│   ├── cleaned_sales.csv           accepted records + financial columns
│   ├── rejected_records.csv        quarantined records with review reasons
│   ├── data_quality_report.csv     one row per issue (ID, column, value, issue, severity, action, status)
│   ├── data_quality_rule_summary.csv  PASS/FAIL for every rule
│   ├── sales_summary.csv           company KPIs
│   ├── city_performance.csv  product_performance.csv  salesperson_performance.csv
│   ├── category_performance.csv  payment_method_performance.csv
│   ├── daily_revenue.csv  transaction_segments.csv  cleaning_summary.csv
│   └── raw_sales_original.csv      untouched copy of the source data for auditing
├── notebooks/sales_analysis.ipynb  # Stages 1–11 with outputs and interpretations
├── src/
│   ├── source_data.py   # ORIGINAL sales dictionary + product reference (never modified)
│   ├── validation.py    # schema validation, data quality rules, business-rule checks
│   ├── cleaning.py      # reusable cleaning functions + documented assumptions A1–A7
│   ├── analytics.py     # financial, aggregation, time-series, segmentation, merge logic
│   └── pipeline.py      # end-to-end orchestration and export
├── tests/test_sales_pipeline.py    # 28 automated pytest tests
├── reports/management_report.md    # management report + final investment recommendation
├── requirements.txt  pytest.ini  .gitignore  README.md
```

## Installation

Requires Python 3.10 or later.

```bash
git clone https://github.com/<your-username>/injiva-pandas-sales-intelligence.git
cd injiva-pandas-sales-intelligence
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS / Linux:        source .venv/bin/activate
pip install -r requirements.txt
```

## Running

Run all commands from the repository root.

| Task | Command |
|---|---|
| Run the full pipeline and regenerate `data/*.csv` | `python -m src.pipeline` |
| Run the automated tests | `python -m pytest -v` |
| Open the analysis notebook | `jupyter notebook notebooks/sales_analysis.ipynb`, then **Kernel → Restart & Run All** |

Expected pipeline headline:
* 17 accepted records and 3 rejected (TX009, TX012, TX015);
* net revenue **$13,340.50**, gross profit **$3,255.50**, overall margin **24.40%**.

## Pipeline steps (`src/pipeline.py`)

1. `construct_dataframe`: checks list lengths and builds the DataFrame from a deep copy of the source.
2. `validate_structure`: checks mandatory columns and expected types. A missing column raises `SchemaValidationError`.
3. `assess_quality`: runs the rule-based data quality report.
4. `clean`: standardises the data, splits accepted and rejected records, and validates business rules.
5. `transform`: adds the financial columns and re-checks them row by row.
6. `aggregate`: builds the grouped performance tables and reconciles each one to the transaction total.
7. `analyse`: produces the KPIs, segmentation and daily time series.
8. `export_outputs`: writes the CSVs, but only after every check above has passed.

## Key data decisions

* **Dates.** Only explicit formats are used: `%Y-%m-%d`, `%d/%m/%Y` and `%d-%m-%Y`. Day-first is assumed because the data covers January 2026 and the dates then run in order with the transaction IDs.
* **Missing price (TX012).** The price is not imputed or zero-filled. The record is quarantined.
* **Negative (TX009) and zero (TX015) quantities.** These are quarantined for manual review, not deleted. A negative quantity may be a return, but it is not linked to an original sale.
* **Product names.** These are converted to title case, and the originals are kept in `Original_Product`.
* **Masvingo.** It has no records, so it is reported as *unknown*, not as zero sales.

## Limitations

* The sample is 17 valid transactions, about one per day, so the findings are indicative only.
* 11 days of January have no records.
* Each salesperson works in only one city, so city and salesperson effects are confounded.
* The figures are gross profit only, because operating costs are not available.

See `reports/management_report.md` for the full discussion.

## Security

`.gitignore` excludes virtual environments, caches, notebook checkpoints, temporary files and `.env`/credential files. No secrets are used or stored in this project.
