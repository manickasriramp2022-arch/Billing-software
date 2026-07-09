from datetime import date

from flask import Blueprint, render_template

from ..db import get_db

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    db = get_db()
    month_start = date.today().replace(day=1).isoformat()

    outstanding = db.execute(
        """SELECT COUNT(*) AS n,
                  COALESCE(SUM((i.total - COALESCE(p.paid, 0)) * i.exchange_rate), 0) AS inr
           FROM invoices i
           LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id) p
                  ON p.invoice_id = i.id
           WHERE i.invoice_type = 'COMMERCIAL' AND i.status = 'ISSUED'
             AND i.total - COALESCE(p.paid, 0) > 0.005"""
    ).fetchone()

    month = db.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(total_inr), 0) AS inr
           FROM invoices
           WHERE invoice_type = 'COMMERCIAL' AND status != 'CANCELLED' AND invoice_date >= ?""",
        (month_start,),
    ).fetchone()

    brc_pending = db.execute(
        """SELECT COUNT(*) FROM invoices
           WHERE invoice_type = 'COMMERCIAL' AND status = 'ISSUED' AND brc_status = 'PENDING'"""
    ).fetchone()[0]

    igst_pending = db.execute(
        """SELECT COUNT(*) FROM invoices
           WHERE invoice_type = 'COMMERCIAL' AND status != 'CANCELLED'
             AND gst_treatment = 'IGST' AND igst_refund_status IN ('PENDING', 'FILED')"""
    ).fetchone()[0]

    recent = db.execute(
        """SELECT i.*, b.name AS buyer_name,
                  COALESCE((SELECT SUM(amount) FROM payments WHERE invoice_id = i.id), 0) AS paid
           FROM invoices i JOIN buyers b ON b.id = i.buyer_id
           ORDER BY i.id DESC LIMIT 8"""
    ).fetchall()

    return render_template("dashboard.html", outstanding=outstanding, month=month,
                           brc_pending=brc_pending, igst_pending=igst_pending, recent=recent)
