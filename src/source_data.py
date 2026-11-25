"""
Original source datasets for the ZimTech Retail Holdings project.

IMPORTANT: These dictionaries are the audited source of truth and must never be
modified in place. Always obtain a working copy with ``get_sales_data()`` or
``get_product_reference()``, which return deep copies.
"""

import copy

# ---------------------------------------------------------------------------
# Original sales dictionary exactly as supplied in the assessment brief
# (assessment reference INJIVA-DS-DA-PANDAS-001). Do NOT edit.
# ---------------------------------------------------------------------------
sales_data = {
    "Transaction_ID": [
        "TX001", "TX002", "TX003", "TX004",
        "TX005", "TX006", "TX007", "TX008",
        "TX009", "TX010", "TX011", "TX012",
        "TX013", "TX014", "TX015", "TX016",
        "TX017", "TX018", "TX019", "TX020",
    ],
    "Date": [
        "2026-01-05", "06/01/2026", "2026-01-07",
        "2026-01-08", "09-01-2026", "2026-01-10",
        "2026-01-11", "12/01/2026", "2026-01-13",
        "2026-01-14", "2026-01-15", "16/01/2026",
        "2026-01-17", "2026-01-18", "19-01-2026",
        "2026-01-20", "2026-01-21", "2026-01-22",
        "2026-01-23", "2026-01-24",
    ],
    "Product": [
        "Laptop", "Smartphone", "keyboard",
        "Monitor", "Printer", "LAPTOP",
        "Mouse", "Smartphone", "monitor",
        "Keyboard", "Laptop", "Printer",
        "Mouse", "Smartphone", "Laptop",
        "Monitor", "Keyboard", "Printer",
        "Smartphone", "Mouse",
    ],
    "Category": [
        "Computers", "Mobile", "Accessories",
        "Computers", "Office Equipment",
        "Computers", "Accessories", "Mobile",
        "Computers", "Accessories",
        "Computers", "Office Equipment",
        "Accessories", "Mobile", "Computers",
        "Computers", "Accessories",
        "Office Equipment", "Mobile",
        "Accessories",
    ],
    "Quantity": [
        2, 5, 10, 3, 2, 1, 15, 4, -2, 8,
        3, 2, 12, 5, 0, 4, 9, 2, 6, 20,
    ],
    "Unit_Price": [
        650, 300, 25, 180, 220,
        700, 15, 320, 200, 30,
        680, None, 18, 310, 670,
        190, 28, 230, 330, 15,
    ],
    "Unit_Cost": [
        500, 220, 12, 130, 160,
        520, 7, 240, 145, 14,
        510, 165, 8, 235, 505,
        140, 13, 170, 250, 7,
    ],
    "Salesperson": [
        "John", "Mary", "Peter", "John",
        "Sarah", "Mary", "Peter", "Sarah",
        "John", "Mary", "John", "Sarah",
        "Peter", "Mary", "John", "Sarah",
        "Peter", "Mary", "Sarah", "Peter",
    ],
    "City": [
        "Bulawayo", "Harare", "Gweru",
        "Bulawayo", "Mutare", "Harare",
        "Gweru", "Mutare", "Bulawayo",
        "Harare", "Bulawayo", "Mutare",
        "Gweru", "Harare", "Bulawayo",
        "Mutare", "Gweru", "Harare",
        "Mutare", "Gweru",
    ],
    "Payment_Method": [
        "Cash", "EcoCash", "Bank Transfer",
        "Cash", "EcoCash", "Bank Transfer",
        "Cash", "EcoCash", "Cash",
        "Bank Transfer", "Cash", "EcoCash",
        "Cash", "Bank Transfer", "Cash",
        "EcoCash", "Cash", "Bank Transfer",
        "EcoCash", "Cash",
    ],
    "Discount_Percent": [
        0, 5, 0, 10, 0, 5, 0, 10, 0, 0,
        5, 0, 0, 5, 10, 0, 0, 5, 10, 0,
    ],
}

# ---------------------------------------------------------------------------
# Product reference data (Stage 8). Created by the analyst. Product names are
# deliberately stored with inconsistent casing/whitespace in two places so that
# name standardisation before merging can be demonstrated. "Tablet" is a
# catalogue item with no January sales, used to demonstrate unmatched records.
# ---------------------------------------------------------------------------
product_reference = {
    "Product_Code": [
        "ZT-CMP-001", "ZT-CMP-002", "ZT-MOB-001", "ZT-ACC-001",
        "ZT-ACC-002", "ZT-OFF-001", "ZT-MOB-002",
    ],
    "Product_Name": [
        "Laptop", "Monitor", "Smartphone", "keyboard",
        " Mouse ", "Printer", "Tablet",
    ],
    "Product_Category": [
        "Computers", "Computers", "Mobile", "Accessories",
        "Accessories", "Office Equipment", "Mobile",
    ],
    "Reorder_Threshold": [5, 4, 6, 10, 15, 3, 4],
}

# Cities in which ZimTech operates (from the business case), including Masvingo,
# which has no records in the supplied sample.
OPERATING_CITIES = ["Bulawayo", "Harare", "Gweru", "Mutare", "Masvingo"]


def get_sales_data():
    """Return an independent deep copy of the original sales dictionary."""
    return copy.deepcopy(sales_data)


def get_product_reference():
    """Return an independent deep copy of the product reference dictionary."""
    return copy.deepcopy(product_reference)
