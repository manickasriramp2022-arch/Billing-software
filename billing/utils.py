"""Formatting and document-number helpers."""
from datetime import date, datetime

CURRENCIES = ["USD", "EUR", "GBP", "SGD", "AED", "MYR", "CNY", "JPY", "AUD", "INR"]
INCOTERMS = ["FOB", "CIF", "CFR", "EXW", "FCA", "CPT", "CIP", "DAP"]

CURRENCY_WORDS = {
    "USD": ("US Dollars", "Cents"),
    "EUR": ("Euros", "Cents"),
    "GBP": ("Pounds Sterling", "Pence"),
    "SGD": ("Singapore Dollars", "Cents"),
    "AED": ("UAE Dirhams", "Fils"),
    "MYR": ("Malaysian Ringgit", "Sen"),
    "CNY": ("Chinese Yuan", "Fen"),
    "JPY": ("Japanese Yen", None),
    "AUD": ("Australian Dollars", "Cents"),
    "INR": ("Indian Rupees", "Paise"),
}

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n):
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n):
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n:
        out.append(_two(n))
    return " ".join(out)


def int_to_words(n, indian=False):
    if n == 0:
        return "Zero"
    parts = []
    if indian:
        for divisor, label in ((10**7, "Crore"), (10**5, "Lakh"), (10**3, "Thousand")):
            if n >= divisor:
                parts.append(int_to_words(n // divisor, indian=True) + " " + label)
                n %= divisor
    else:
        for divisor, label in ((10**9, "Billion"), (10**6, "Million"), (10**3, "Thousand")):
            if n >= divisor:
                parts.append(_three(n // divisor) + " " + label)
                n %= divisor
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def amount_in_words(amount, currency):
    """e.g. 1234.50 USD -> 'US Dollars One Thousand Two Hundred Thirty Four and Cents Fifty Only'."""
    major_name, minor_name = CURRENCY_WORDS.get(currency, (currency, "Cents"))
    indian = currency == "INR"
    amount = round(float(amount or 0), 2)
    major = int(amount)
    minor = int(round((amount - major) * 100))
    if minor_name is None:  # zero-decimal currency
        major, minor = int(round(amount)), 0
    words = f"{major_name} {int_to_words(major, indian=indian)}"
    if minor:
        words += f" and {minor_name} {int_to_words(minor, indian=indian)}"
    return words + " Only"


def money(value):
    """1234567.5 -> '1,234,567.50' (western grouping)."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def inr(value):
    """1234567.5 -> '12,34,567.50' (Indian grouping)."""
    try:
        value = round(float(value), 2)
    except (TypeError, ValueError):
        value = 0.0
    sign = "-" if value < 0 else ""
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}{whole}.{frac}"


def qty(value):
    """Format a quantity: trim trailing zeros but keep up to 2 decimals."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0"
    text = f"{value:,.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_date(value):
    """ISO date -> DD-MM-YYYY for documents."""
    if not value:
        return ""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return str(value)


def fiscal_year(iso_date=None):
    """Indian fiscal year label, e.g. 2026-04-01 -> '2026-27'."""
    d = datetime.strptime(iso_date, "%Y-%m-%d").date() if iso_date else date.today()
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def next_invoice_number(db, invoice_type, iso_date, settings):
    fy = fiscal_year(iso_date)
    prefix = settings.get("prefix_proforma" if invoice_type == "PROFORMA" else "prefix_commercial") or invoice_type[:2]
    row = db.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM invoices WHERE invoice_type = ? AND fy = ?",
        (invoice_type, fy),
    ).fetchone()
    seq = row[0]
    return f"{prefix}/{fy}/{seq:03d}", fy, seq


def parse_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip() or default)
    except (TypeError, ValueError):
        return default
