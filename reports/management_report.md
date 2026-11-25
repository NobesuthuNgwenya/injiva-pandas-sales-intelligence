# ZimTech Retail Holdings — January 2026 Sales Intelligence Report

**Prepared for:** Finance, Operations and Executive Management
**Prepared by:** Trainee Data Engineer / Data Analyst, INJIVA Digital Systems — Data & Analytics
**Assessment reference:** INJIVA-DS-DA-PANDAS-001
**Data:** 20 fictional transactions, 5–24 January 2026, USD

All figures below come from `python -m src.pipeline` and match the CSV files in `data/`.
**Facts** are stated plainly. **Interpretations** and **recommendations** are labelled as such.

---

## 1. Executive summary

* **17 of 20 transactions are valid.** 3 (15%) are quarantined for manual review because of a negative quantity, a zero quantity and a missing selling price.
* On the valid records, **net revenue is $13,340.50, gross profit is $3,255.50 and the overall gross profit margin is 24.40%**. Average transaction value is $784.74, and no transaction made a loss.
* **Discounts cost $692.50 (4.93% of gross revenue).** The three 10% discounts produced the three lowest margins in the dataset.
* **Answer to the management challenge** (details in Section 10):
  * **City: Harare.** Highest net revenue and gross profit, the most diversified product mix and no quarantined records.
  * **Category: Computers.** Highest gross profit at a better margin than Mobile, and less dependence on discounts.
  * **Salesperson: Mary.** Highest revenue and profit, and no data quality issues.
* **Main caveat:** each salesperson works in only one city, so city and salesperson performance cannot be separated. The sample is 17 transactions over 20 days, so these findings are indicative and should be confirmed with more data.

## 2. Data quality findings

18 automated rules were run (`data/data_quality_rule_summary.csv`). 12 passed with zero violations. 13 issues were logged in `data/data_quality_report.csv`.

| Transaction | Issue | Severity | Treatment | Financial effect |
|---|---|---|---|---|
| TX009 | Quantity = −2 (Monitor, Bulawayo, John) | High | Quarantined; may be a return, but no original sale is referenced | If booked as a return: −$400.00 revenue, −$110.00 gross profit |
| TX012 | Unit_Price missing (Printer ×2, Mutare, Sarah) | High | Quarantined; **not** imputed or zero-filled | Unknown. At observed Printer prices ($220–$230) ≈ $440–$460 revenue (≈3.3% of net revenue). Indicative only, not booked |
| TX015 | Quantity = 0 (Laptop, Bulawayo, John) | Medium | Quarantined; possibly a cancelled transaction | None |
| TX003, TX006, TX009 | Product names `keyboard`, `LAPTOP`, `monitor` | Low | Standardised to title case | Without this fix, Laptop revenue would be split across two names |
| TX002, TX005, TX008, TX012, TX015 | Day-first dates (`06/01/2026`, `09-01-2026`) | Low | Parsed with explicit formats `%d/%m/%Y` and `%d-%m-%Y` | Avoids wrongly placing sales in June, September or December |
| Column-level | `Date` stored as text; `Unit_Price` coerced to float | Medium/Low | Converted to datetime / kept as float currency | — |

No duplicate transaction IDs, duplicate rows, invalid costs, prices below cost, out-of-range discounts or product-category conflicts were found.

**Interpretation:** two of the three quarantined records came from Bulawayo/John, and both are Computers products. This points to a data entry or process issue at that point of sale.

## 3. Revenue and profitability analysis

| Metric | Value |
|---|---|
| Valid transactions | 17 |
| Units sold | 111 |
| Gross revenue | $14,033.00 |
| Discounts | $692.50 |
| **Net revenue** | **$13,340.50** |
| Total cost | $10,085.00 |
| **Gross profit** | **$3,255.50** |
| **Overall gross profit margin** (total GP ÷ total NR) | **24.40%** |
| Average transaction value | $784.74 |
| Loss-making transactions | 0 |

The margin is calculated from totals. Averaging the individual transaction margins would overstate it at 32.83%, because the many small, high-margin accessory sales would count as much as the large sales.
Figures are **gross** profit. Operating expenses (rent, salaries etc.) are not in the data, so net profit cannot be calculated.

**Discount effect (fact):**

| Discount | Transactions | Net revenue | Gross profit | Margin |
|---|---|---|---|---|
| 0% | 9 | $3,983.00 | $1,413.00 | 35.5% |
| 5% | 5 | $5,937.50 | $1,272.50 | 21.4% |
| 10% | 3 | $3,420.00 | $570.00 | 16.7% |

**Interpretation:** higher discounts go with lower margins. Discounts are also applied mainly to high-value, lower-margin products, so part of this pattern comes from the product mix rather than the discount itself. This is a correlation, not proof that discounts cause lower margins.

## 4. Product performance findings (`data/product_performance.csv`)

| Product | Units | Net revenue | Gross profit | Margin | Class |
|---|---|---|---|---|---|
| Smartphone | 20 | $5,831.50 | $1,096.50 | 18.8% | Volume Driver |
| Laptop | 6 | $3,903.00 | $853.00 | 21.9% | Volume Driver |
| Monitor | 7 | $1,246.00 | $296.00 | 23.8% | Underperformer |
| Printer | 4 | $877.00 | $217.00 | 24.7% | Margin Niche |
| Keyboard | 27 | $742.00 | $393.00 | 53.0% | Margin Niche |
| Mouse | 47 | $741.00 | $400.00 | 54.0% | Margin Niche |

*Classes compare each product's revenue with the average product revenue and its margin with the overall 24.40% margin.*

* Smartphone brings in 43.7% of revenue but has the lowest margin, and it carries 69% of all discount value ($478.50).
* Mouse and Keyboard account for 67% of units but only 11% of revenue. Ranking products by quantity would therefore be misleading.
* **By category:** Mobile has the most revenue ($5,831.50). Computers has the most **gross profit** ($1,149.00, 22.3% margin). Accessories has the highest margin (53.5%) and volume (74 units). Office Equipment is the smallest ($877.00).
* Tablet (ZT-MOB-002) is in the product catalogue but had no recorded sales in this sample.

## 5. City-level performance findings (`data/city_performance.csv`)

| City | Transactions | Net revenue | Gross profit | Margin | Revenue share |
|---|---|---|---|---|---|
| Harare | 5 | $4,239.50 | $992.50 | 23.4% | 31.8% |
| Mutare | 4 | $4,134.00 | $794.00 | 19.2% | 31.0% |
| Bulawayo | 3 | $3,724.00 | $804.00 | 21.6% | 27.9% |
| Gweru | 5 | $1,243.00 | $665.00 | 53.5% | 9.3% |
| Masvingo | — | unknown | unknown | — | — |

* Harare ranks first on both revenue and profit, and sells across all four categories.
* Mutare is second on revenue but third on profit. It has the lowest margin, because two of its four sales were Smartphones at a 10% discount.
* Bulawayo sold only Computers, and Gweru only Accessories.
* **Masvingo has no records in the sample.** This means its activity is unknown, not that it sold nothing.

## 6. Salesperson performance findings (`data/salesperson_performance.csv`)

| Salesperson | City | Transactions | Net revenue | Gross profit | Margin | Avg discount |
|---|---|---|---|---|---|---|
| Mary | Harare | 5 | $4,239.50 | $992.50 | 23.4% | 4.0% |
| Sarah | Mutare | 4 | $4,134.00 | $794.00 | 19.2% | 5.0% |
| John | Bulawayo | 3 | $3,724.00 | $804.00 | 21.6% | 5.0% |
| Peter | Gweru | 5 | $1,243.00 | $665.00 | 53.5% | 0.0% |

* The average revenue per salesperson is $3,335.13. Only Peter is below it, but he has the highest margin and gives no discounts.
* Sarah gave 47% of all discount value ($326.00), which explains her lower margin.
* John has the highest average transaction value ($1,241.33), but 2 of the 3 quarantined records are his.
* **Interpretation:** salesperson and city results are identical because each person sold in only one city. It is impossible to tell whether results come from the person or the market.

## 7. Actionable business recommendations

1. **Set a discount approval rule for Mobile products.** 10% discounts produced the lowest margins (15.8–16.7% on Smartphones). *Illustration only:* capping TX008 and TX019 at 5% would have added $163.00 of gross profit (+5.0%), assuming the sales still happened at that discount.
2. **Fix point-of-sale validation, starting in Bulawayo.** Block zero or negative quantities unless they are flagged as a return linked to an original sale, and make the selling price mandatory. Data problems affected 15% of records in this sample.
3. **Resolve the three quarantined records with Finance.** In particular, recover TX012's invoiced price (≈$440–$460 of revenue at risk), then re-run the pipeline.
4. **Prioritise Harare, Computers and Mary for investment and stock**, as set out in Section 10, and use Harare's mixed-category approach as the model for other branches.
5. **Use accessories to raise margins in high-revenue branches.** Accessories earn 53% margins but are sold almost only in Gweru. *Hypothesis to test:* bundling a mouse or keyboard with Laptop and Smartphone sales in Harare, Mutare and Bulawayo.
6. **Rotate or share salespeople across cities, and start collecting Masvingo data.** This would separate salesperson effects from market effects and show whether the fifth branch is trading.
7. **Use the product reference table for stock control.** Track units sold against reorder thresholds (e.g. Mouse sold 47 units against a threshold of 15) and check why Tablet had no sales.

## 8. Dataset limitations and assumptions

* **Small sample.** 17 valid transactions over 20 days, about one sale per day. One large sale can change any ranking: removing TX014 alone ($1,472.50) would drop Harare from 1st to 3rd. No statistical significance is claimed.
* **Coverage.** 11 days of January (1–4 and 25–31) have no records, and 3 more days have only quarantined records. Monthly totals are therefore incomplete, and missing days are treated as unknown, not as zero sales.
* **Masvingo is absent.** Its performance is unknown.
* **Confounding.** Each salesperson works in one city, so their effects cannot be separated.
* **Gross profit only.** Operating costs are not in the data.
* **Assumptions.** Dates are day-first (DD/MM/YYYY). Unit costs are accurate. Discounts apply to the whole line. Negative and zero quantities are excluded until verified. Missing prices are never imputed. All data is fictional.

## 9. Technical implementation summary

* **Modules:** `src/source_data.py` (original dictionaries, kept unmodified), `src/validation.py` (schema and 18 data quality rules), `src/cleaning.py` (deterministic cleaning, documented rules A1–A7, accept/reject split), `src/analytics.py` (financial, aggregation, time-series, segmentation and merge functions), `src/pipeline.py` (8-step orchestration; exports only after validation).
* **Controls:**
  * Financials are re-checked row by row with independent arithmetic, within a tolerance of 1e-6.
  * Every grouped table is reconciled to the transaction total.
  * Merges use `validate="many_to_one"`, and row counts and revenue are compared before and after.
  * Division by zero returns NaN.
* **Tests:** 28 pytest tests in `tests/test_sales_pipeline.py`. They use hand-calculated expected values, cover boundary values (quantity 1, discount 0% and 100%) and include a deliberately invalid record (TX999), which is caught.
* **Tools:** Python 3, pandas, NumPy, Jupyter and pytest. No visualisation libraries are used.

## 10. Final challenge: where should ZimTech invest?

> *"Based on the available sales records, which city, product category and salesperson should ZimTech Retail Holdings prioritise for future investment, and what evidence supports your recommendation?"*

**Recommendation: Harare (city), Computers (category) and Mary (salesperson).** These are provisional and should be re-tested once a full quarter of clean data is available.

| Factor | Harare | Computers | Mary |
|---|---|---|---|
| Net revenue | **1st** — $4,239.50 (31.8%) | 2nd — $5,149.00 (38.6%), vs Mobile $5,831.50 | **1st** — $4,239.50 |
| Gross profit | **1st** — $992.50 | **1st** — $1,149.00 | **1st** — $992.50 |
| Margin | 23.4% (2nd of the three large cities; Gweru's 53.5% comes from a small accessories base) | 22.3% vs Mobile 18.8% | 23.4% vs Sarah 19.2%, John 21.6% |
| Transaction volume | 5 transactions (joint highest), 21 units | 5 transactions, 13 units | 5 transactions |
| Product mix | 4 categories, the most diversified | Laptop $3,903 + Monitor $1,246 | Sells Mobile, Computers, Accessories and Office Equipment |
| Data quality | 0 quarantined records | 2 quarantined records (TX009, TX015) — needs process fixes | 0 quarantined records |
| Discount dependence | Moderate (4.0% average) | Low (3.6% effective) | Moderate, never above 5% |

**Why not the alternatives?**

* **Mobile** has more revenue, but less gross profit and the weakest margin, because its revenue relies on 5–10% discounts. It becomes the stronger option only if a discount cap is introduced (Recommendation 1).
* **Mutare / Sarah** are nearly level with Harare on revenue, but earn $198.50 less gross profit because of discounting.
* **Gweru / Peter** have excellent margins but only 9.3% of revenue. They are better used as a source of accessory-selling practice than as an investment priority.

**Operational risks:**

* The Harare/Mary result cannot be split into a market effect and a salesperson effect.
* Computers' two quarantined records show a data capture risk in Bulawayo.
* The lead is small: Harare is ahead of Mutare by only $105.50 in revenue.

**Evidence and reproducibility:** run `python -m src.pipeline` and see `city_performance.csv`, `category_performance.csv` and `salesperson_performance.csv`, or Stages 5 and 9 of `notebooks/sales_analysis.ipynb`.

## 11. Reproduction instructions

```bash
git clone https://github.com/<your-username>/injiva-pandas-sales-intelligence.git
cd injiva-pandas-sales-intelligence
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline          # regenerates every CSV in data/
python -m pytest -v             # 28 tests should pass
jupyter notebook notebooks/sales_analysis.ipynb   # Kernel -> Restart & Run All
```
