from datetime import date

from flask import Blueprint, render_template, request

from ..db import get_db

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/outstanding")
def outstanding():
    """Issued commercial invoices with a balance due, with ageing."""
    db = get_db()
    rows = db.execute(
        """SELECT i.*, b.name AS buyer_name, COALESCE(p.paid, 0) AS paid,
                  i.total - COALESCE(p.paid, 0) AS balance,
                  CAST(julianday('now') - julianday(i.invoice_date) AS INTEGER) AS age_days
           FROM invoices i
           JOIN buyers b ON b.id = i.buyer_id
           LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id) p
                  ON p.invoice_id = i.id
           WHERE i.invoice_type = 'COMMERCIAL' AND i.status = 'ISSUED'
             AND i.total - COALESCE(p.paid, 0) > 0.005
           ORDER BY i.invoice_date"""
    ).fetchall()
    total_inr = sum(r["balance"] * r["exchange_rate"] for r in rows)
    by_currency = {}
    for r in rows:
        by_currency[r["currency"]] = by_currency.get(r["currency"], 0) + r["balance"]
    return render_template("reports/outstanding.html", rows=rows,
                           total_inr=total_inr, by_currency=by_currency)


@bp.route("/monthly")
def monthly():
    """Month-wise export summary from non-cancelled commercial invoices."""
    db = get_db()
    rows = db.execute(
        """SELECT strftime('%Y-%m', i.invoice_date) AS month, i.currency,
                  COUNT(*) AS n, SUM(i.total) AS total, SUM(i.total_inr) AS total_inr,
                  SUM((SELECT COALESCE(SUM(quantity), 0) FROM invoice_items WHERE invoice_id = i.id)) AS qty,
                  SUM((SELECT COALESCE(SUM(boxes), 0) FROM invoice_items WHERE invoice_id = i.id)) AS boxes
           FROM invoices i
           WHERE i.invoice_type = 'COMMERCIAL' AND i.status != 'CANCELLED'
           GROUP BY month, i.currency
           ORDER BY month DESC, i.currency"""
    ).fetchall()
    months = {}
    for r in rows:
        m = months.setdefault(r["month"], {"lines": [], "inr": 0, "n": 0, "qty": 0, "boxes": 0})
        m["lines"].append(r)
        m["inr"] += r["total_inr"] or 0
        m["n"] += r["n"]
        m["qty"] += r["qty"] or 0
        m["boxes"] += r["boxes"] or 0
    return render_template("reports/monthly.html", months=months)


@bp.route("/buyer-ledger")
def buyer_ledger():
    """Chronological invoice/payment ledger with running balance, per buyer."""
    db = get_db()
    buyers = db.execute("SELECT id, name, currency FROM buyers ORDER BY name").fetchall()
    buyer_id = request.args.get("buyer_id", "")
    buyer, entries = None, []
    if buyer_id.isdigit():
        buyer = db.execute("SELECT * FROM buyers WHERE id = ?", (int(buyer_id),)).fetchone()
    if buyer:
        invoices = db.execute(
            """SELECT * FROM invoices
               WHERE buyer_id = ? AND invoice_type = 'COMMERCIAL' AND status != 'CANCELLED'
               ORDER BY invoice_date""",
            (buyer["id"],),
        ).fetchall()
        for inv in invoices:
            entries.append({"date": inv["invoice_date"], "ref": inv["invoice_no"],
                            "kind": "Invoice", "currency": inv["currency"],
                            "debit": inv["total"], "credit": 0, "invoice_id": inv["id"]})
            for p in db.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date", (inv["id"],)
            ):
                entries.append({"date": p["payment_date"],
                                "ref": p["bank_reference"] or f"Payment ({p['kind'].title()})",
                                "kind": "Payment", "currency": inv["currency"],
                                "debit": 0, "credit": p["amount"], "invoice_id": inv["id"]})
        entries.sort(key=lambda e: (e["date"], e["kind"] == "Payment"))
        balance = 0.0
        for e in entries:
            balance = round(balance + e["debit"] - e["credit"], 2)
            e["balance"] = balance
    return render_template("reports/buyer_ledger.html", buyers=buyers, buyer=buyer,
                           entries=entries, selected=buyer_id)


@bp.route("/compliance")
def compliance():
    """BRC realization tracker and IGST refund tracker."""
    db = get_db()
    brc = db.execute(
        """SELECT i.*, b.name AS buyer_name
           FROM invoices i JOIN buyers b ON b.id = i.buyer_id
           WHERE i.invoice_type = 'COMMERCIAL' AND i.status = 'ISSUED'
           ORDER BY i.brc_status DESC, i.invoice_date"""
    ).fetchall()
    igst = db.execute(
        """SELECT i.*, b.name AS buyer_name
           FROM invoices i JOIN buyers b ON b.id = i.buyer_id
           WHERE i.invoice_type = 'COMMERCIAL' AND i.status != 'CANCELLED'
             AND i.gst_treatment = 'IGST'
           ORDER BY i.igst_refund_status, i.invoice_date"""
    ).fetchall()
    return render_template("reports/compliance.html", brc=brc, igst=igst,
                           today=date.today().isoformat())
