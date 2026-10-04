"""A plain starting chart of accounts. Codes and names are only a start: the workspace's
accountant renames, adds and switches off accounts to suit their country and business.
Roles tell the automatic postings where things go."""

from __future__ import annotations

# (code, name, type, role)
STARTING_CHART: tuple[tuple[str, str, str, str | None], ...] = (
    ("1000", "Cash in hand", "asset", "cash"),
    ("1010", "Till cash", "asset", "drawer"),
    ("1020", "Petty cash", "asset", "petty_cash"),
    ("1100", "Bank and mobile money", "asset", "bank"),
    ("1200", "Customers who owe us", "asset", "receivables"),
    ("1300", "Stock", "asset", "inventory"),
    ("1400", "Tax we can reclaim", "asset", "tax_receivable"),
    ("2000", "Suppliers we owe", "liability", "payables"),
    ("2100", "Tax collected, to pay", "liability", "tax_payable"),
    ("2200", "Salaries to pay", "liability", "salaries_payable"),
    ("2210", "Payroll deductions to pay", "liability", "deductions_payable"),
    ("3000", "Owner's capital", "equity", "capital"),
    ("3100", "Opening balances", "equity", "opening"),
    ("3900", "Retained earnings", "equity", "retained"),
    ("4000", "Sales", "income", "sales"),
    ("4900", "Rounding", "income", "rounding"),
    ("5000", "Cost of goods sold", "expense", "cogs"),
    ("5100", "Stock adjustments", "expense", "stock_adjustments"),
    ("6000", "General expenses", "expense", "expenses"),
    ("6100", "Salaries and wages", "expense", "salaries"),
    ("6900", "Bad debts and write-offs", "expense", "write_offs"),
)
