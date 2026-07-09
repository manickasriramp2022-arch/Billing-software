from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..db import get_db
from ..utils import CURRENCIES, INCOTERMS

bp = Blueprint("buyers", __name__, url_prefix="/buyers")

FIELDS = ["name", "address", "city", "country", "contact_person", "email", "phone",
          "currency", "incoterm", "port_of_discharge", "payment_terms", "notes"]


def _form_values():
    values = {f: request.form.get(f, "").strip() for f in FIELDS}
    values["currency"] = values["currency"] or "USD"
    values["incoterm"] = values["incoterm"] or "FOB"
    return values


@bp.route("/")
def index():
    db = get_db()
    rows = db.execute(
        """SELECT b.*, COUNT(i.id) AS invoice_count
           FROM buyers b LEFT JOIN invoices i ON i.buyer_id = b.id
           WHERE b.active = 1 GROUP BY b.id ORDER BY b.name"""
    ).fetchall()
    return render_template("buyers/list.html", buyers=rows)


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        values = _form_values()
        if not values["name"]:
            flash("Buyer name is required.", "error")
        else:
            db = get_db()
            db.execute(
                f"INSERT INTO buyers ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                [values[f] for f in FIELDS],
            )
            db.commit()
            flash(f"Buyer “{values['name']}” added.", "success")
            return redirect(url_for("buyers.index"))
    return render_template("buyers/form.html", buyer=None,
                           currencies=CURRENCIES, incoterms=INCOTERMS)


@bp.route("/<int:buyer_id>/edit", methods=["GET", "POST"])
def edit(buyer_id):
    db = get_db()
    buyer = db.execute("SELECT * FROM buyers WHERE id = ?", (buyer_id,)).fetchone()
    if buyer is None:
        flash("Buyer not found.", "error")
        return redirect(url_for("buyers.index"))
    if request.method == "POST":
        values = _form_values()
        if not values["name"]:
            flash("Buyer name is required.", "error")
        else:
            db.execute(
                "UPDATE buyers SET " + ", ".join(f"{f} = ?" for f in FIELDS) + " WHERE id = ?",
                [values[f] for f in FIELDS] + [buyer_id],
            )
            db.commit()
            flash("Buyer updated.", "success")
            return redirect(url_for("buyers.index"))
    return render_template("buyers/form.html", buyer=buyer,
                           currencies=CURRENCIES, incoterms=INCOTERMS)


@bp.route("/<int:buyer_id>/delete", methods=["POST"])
def delete(buyer_id):
    db = get_db()
    used = db.execute("SELECT COUNT(*) FROM invoices WHERE buyer_id = ?", (buyer_id,)).fetchone()[0]
    if used:
        db.execute("UPDATE buyers SET active = 0 WHERE id = ?", (buyer_id,))
        flash("Buyer has invoices, so it was archived instead of deleted.", "success")
    else:
        db.execute("DELETE FROM buyers WHERE id = ?", (buyer_id,))
        flash("Buyer deleted.", "success")
    db.commit()
    return redirect(url_for("buyers.index"))
