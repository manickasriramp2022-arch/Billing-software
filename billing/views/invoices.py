from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..db import get_db, get_settings
from ..utils import CURRENCIES, INCOTERMS, next_invoice_number, parse_float

bp = Blueprint("invoices", __name__, url_prefix="/invoices")

HEADER_FIELDS = [
    "invoice_date", "currency", "exchange_rate", "incoterm", "payment_terms",
    "port_of_loading", "port_of_discharge", "country_of_origin", "final_destination",
    "vessel_flight_no", "container_no", "shipping_bill_no", "shipping_bill_date",
    "lc_reference", "marks_and_numbers", "gst_treatment", "lut_arn", "igst_rate",
    "igst_refund_status", "brc_status", "brc_no", "brc_date", "notes",
]
FLOAT_FIELDS = {"exchange_rate", "igst_rate"}


def payment_summary(db, invoice):
    paid = db.execute(
        "SELECT COALESCE(SUM(amount), 0), COALESCE(SUM(amount_inr), 0)"
        " FROM payments WHERE invoice_id = ?", (invoice["id"],)
    ).fetchone()
    balance = round(invoice["total"] - paid[0], 2)
    if invoice["status"] == "CANCELLED":
        label = "Cancelled"
    elif invoice["status"] == "DRAFT":
        label = "Draft"
    elif invoice["invoice_type"] == "PROFORMA":
        label = "Issued"
    elif invoice["total"] > 0 and balance <= 0.005:
        label = "Paid"
    elif paid[0] > 0:
        label = "Part-paid"
    else:
        label = "Unpaid"
    return {"paid": paid[0], "paid_inr": paid[1], "balance": balance, "label": label}


def _parse_items(form, settings):
    """Read parallel item arrays from the invoice form; skip fully empty rows."""
    items = []
    descriptions = form.getlist("item_description[]")
    for i, description in enumerate(descriptions):
        def field(name, cast=None):
            values = form.getlist(f"item_{name}[]")
            raw = values[i].strip() if i < len(values) else ""
            return parse_float(raw) if cast else raw

        row = {
            "product_id": field("product_id") or None,
            "description": description.strip(),
            "hs_code": field("hs_code") or settings.get("default_hs_code", ""),
            "boxes": field("boxes", float),
            "net_weight": field("net_weight", float),
            "gross_weight": field("gross_weight", float),
            "quantity": field("quantity", float),
            "unit": field("unit") or "KG",
            "unit_price": field("unit_price", float),
        }
        if not row["description"] and not row["quantity"] and not row["unit_price"]:
            continue
        row["amount"] = round(row["quantity"] * row["unit_price"], 2)
        items.append(row)
    return items


def _totals(items, form):
    subtotal = round(sum(item["amount"] for item in items), 2)
    freight = parse_float(form.get("freight_amount"))
    insurance = parse_float(form.get("insurance_amount"))
    total = round(subtotal + freight + insurance, 2)
    fx = parse_float(form.get("exchange_rate"), 1) or 1
    total_inr = round(total * fx, 2)
    igst_rate = parse_float(form.get("igst_rate"))
    igst_inr = round(total_inr * igst_rate / 100, 2) if form.get("gst_treatment") == "IGST" else 0
    return subtotal, freight, insurance, total, total_inr, igst_inr


def _save_items(db, invoice_id, items):
    db.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    for order, item in enumerate(items):
        db.execute(
            """INSERT INTO invoice_items
               (invoice_id, product_id, description, hs_code, boxes, net_weight,
                gross_weight, quantity, unit, unit_price, amount, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (invoice_id, item["product_id"], item["description"], item["hs_code"],
             item["boxes"], item["net_weight"], item["gross_weight"], item["quantity"],
             item["unit"], item["unit_price"], item["amount"], order),
        )


def _form_context(db, invoice=None, items=None):
    return {
        "invoice": invoice,
        "items": items or [],
        "buyers": db.execute("SELECT * FROM buyers WHERE active = 1 ORDER BY name").fetchall(),
        "products": db.execute("SELECT * FROM products WHERE active = 1 ORDER BY name, grade").fetchall(),
        "settings": get_settings(db),
        "currencies": CURRENCIES,
        "incoterms": INCOTERMS,
        "today": date.today().isoformat(),
    }


@bp.route("/")
def index():
    db = get_db()
    where, params = ["1=1"], []
    invoice_type = request.args.get("type", "")
    status = request.args.get("status", "")
    buyer_id = request.args.get("buyer_id", "")
    if invoice_type in ("PROFORMA", "COMMERCIAL"):
        where.append("i.invoice_type = ?")
        params.append(invoice_type)
    if status in ("DRAFT", "ISSUED", "CANCELLED"):
        where.append("i.status = ?")
        params.append(status)
    if buyer_id.isdigit():
        where.append("i.buyer_id = ?")
        params.append(int(buyer_id))
    rows = db.execute(
        f"""SELECT i.*, b.name AS buyer_name,
                   COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) AS paid
            FROM invoices i JOIN buyers b ON b.id = i.buyer_id
            WHERE {' AND '.join(where)}
            ORDER BY i.invoice_date DESC, i.id DESC""",
        params,
    ).fetchall()
    buyers = db.execute("SELECT id, name FROM buyers ORDER BY name").fetchall()
    return render_template("invoices/list.html", invoices=rows, buyers=buyers,
                           f_type=invoice_type, f_status=status, f_buyer=buyer_id)


@bp.route("/new", methods=["GET", "POST"])
def create():
    db = get_db()
    settings = get_settings(db)
    invoice_type = (request.values.get("type") or "COMMERCIAL").upper()
    if invoice_type not in ("PROFORMA", "COMMERCIAL"):
        invoice_type = "COMMERCIAL"

    if request.method == "POST":
        buyer_id = request.form.get("buyer_id", "")
        if not buyer_id.isdigit():
            flash("Choose a buyer (add one under Buyers first).", "error")
            return redirect(url_for("invoices.create", type=invoice_type))
        items = _parse_items(request.form, settings)
        subtotal, freight, insurance, total, total_inr, igst_inr = _totals(items, request.form)
        invoice_date = request.form.get("invoice_date") or date.today().isoformat()
        invoice_no, fy, seq = next_invoice_number(db, invoice_type, invoice_date, settings)
        values = {f: request.form.get(f, "").strip() for f in HEADER_FIELDS}
        for f in FLOAT_FIELDS:
            values[f] = parse_float(values[f], 1 if f == "exchange_rate" else 0)
        cur = db.execute(
            f"""INSERT INTO invoices
                (invoice_type, invoice_no, fy, seq, buyer_id, subtotal, freight_amount,
                 insurance_amount, total, total_inr, igst_amount_inr,
                 {', '.join(HEADER_FIELDS)})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {', '.join('?' * len(HEADER_FIELDS))})""",
            [invoice_type, invoice_no, fy, seq, int(buyer_id), subtotal, freight,
             insurance, total, total_inr, igst_inr] + [values[f] for f in HEADER_FIELDS],
        )
        _save_items(db, cur.lastrowid, items)
        db.commit()
        flash(f"{invoice_type.title()} invoice {invoice_no} created as draft.", "success")
        return redirect(url_for("invoices.view", invoice_id=cur.lastrowid))

    context = _form_context(db)
    context["invoice_type"] = invoice_type
    return render_template("invoices/form.html", **context)


@bp.route("/<int:invoice_id>")
def view(invoice_id):
    db = get_db()
    invoice = db.execute(
        """SELECT i.*, b.name AS buyer_name, b.country AS buyer_country
           FROM invoices i JOIN buyers b ON b.id = i.buyer_id WHERE i.id = ?""",
        (invoice_id,),
    ).fetchone()
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    items = db.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY sort_order", (invoice_id,)
    ).fetchall()
    payments = db.execute(
        "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date, id", (invoice_id,)
    ).fetchall()
    commercial = None
    if invoice["invoice_type"] == "PROFORMA":
        commercial = db.execute(
            "SELECT id, invoice_no FROM invoices WHERE proforma_id = ? AND status != 'CANCELLED'",
            (invoice_id,),
        ).fetchone()
    return render_template("invoices/view.html", invoice=invoice, items=items,
                           payments=payments, summary=payment_summary(db, invoice),
                           commercial=commercial, today=date.today().isoformat())


@bp.route("/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit(invoice_id):
    db = get_db()
    settings = get_settings(db)
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    if invoice["status"] == "CANCELLED":
        flash("Cancelled invoices cannot be edited.", "error")
        return redirect(url_for("invoices.view", invoice_id=invoice_id))

    if request.method == "POST":
        buyer_id = request.form.get("buyer_id", "")
        if not buyer_id.isdigit():
            flash("Choose a buyer.", "error")
            return redirect(url_for("invoices.edit", invoice_id=invoice_id))
        items = _parse_items(request.form, settings)
        subtotal, freight, insurance, total, total_inr, igst_inr = _totals(items, request.form)
        values = {f: request.form.get(f, "").strip() for f in HEADER_FIELDS}
        for f in FLOAT_FIELDS:
            values[f] = parse_float(values[f], 1 if f == "exchange_rate" else 0)
        db.execute(
            "UPDATE invoices SET buyer_id = ?, subtotal = ?, freight_amount = ?,"
            " insurance_amount = ?, total = ?, total_inr = ?, igst_amount_inr = ?, "
            + ", ".join(f"{f} = ?" for f in HEADER_FIELDS) + " WHERE id = ?",
            [int(buyer_id), subtotal, freight, insurance, total, total_inr, igst_inr]
            + [values[f] for f in HEADER_FIELDS] + [invoice_id],
        )
        _save_items(db, invoice_id, items)
        db.commit()
        flash("Invoice updated.", "success")
        return redirect(url_for("invoices.view", invoice_id=invoice_id))

    items = db.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY sort_order", (invoice_id,)
    ).fetchall()
    context = _form_context(db, invoice, items)
    context["invoice_type"] = invoice["invoice_type"]
    return render_template("invoices/form.html", **context)


@bp.route("/<int:invoice_id>/status", methods=["POST"])
def set_status(invoice_id):
    action = request.form.get("action")
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    if action == "issue" and invoice["status"] == "DRAFT":
        db.execute("UPDATE invoices SET status = 'ISSUED' WHERE id = ?", (invoice_id,))
        flash(f"Invoice {invoice['invoice_no']} issued.", "success")
    elif action == "cancel" and invoice["status"] != "CANCELLED":
        db.execute("UPDATE invoices SET status = 'CANCELLED' WHERE id = ?", (invoice_id,))
        flash(f"Invoice {invoice['invoice_no']} cancelled.", "success")
    elif action == "delete" and invoice["status"] == "DRAFT":
        db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        db.commit()
        flash(f"Draft {invoice['invoice_no']} deleted.", "success")
        return redirect(url_for("invoices.index"))
    else:
        flash("That action is not allowed for this invoice.", "error")
    db.commit()
    return redirect(url_for("invoices.view", invoice_id=invoice_id))


@bp.route("/<int:invoice_id>/convert", methods=["POST"])
def convert(invoice_id):
    """Clone a proforma into a draft commercial invoice."""
    db = get_db()
    settings = get_settings(db)
    proforma = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if proforma is None or proforma["invoice_type"] != "PROFORMA":
        flash("Only proforma invoices can be converted.", "error")
        return redirect(url_for("invoices.index"))
    existing = db.execute(
        "SELECT id FROM invoices WHERE proforma_id = ? AND status != 'CANCELLED'", (invoice_id,)
    ).fetchone()
    if existing:
        flash("A commercial invoice already exists for this proforma.", "error")
        return redirect(url_for("invoices.view", invoice_id=existing["id"]))

    today = date.today().isoformat()
    invoice_no, fy, seq = next_invoice_number(db, "COMMERCIAL", today, settings)
    copy_fields = [f for f in HEADER_FIELDS if f != "invoice_date"]
    cur = db.execute(
        f"""INSERT INTO invoices
            (invoice_type, invoice_no, fy, seq, buyer_id, invoice_date, proforma_id,
             subtotal, freight_amount, insurance_amount, total, total_inr, igst_amount_inr,
             {', '.join(copy_fields)})
            VALUES ('COMMERCIAL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    {', '.join('?' * len(copy_fields))})""",
        [invoice_no, fy, seq, proforma["buyer_id"], today, invoice_id,
         proforma["subtotal"], proforma["freight_amount"], proforma["insurance_amount"],
         proforma["total"], proforma["total_inr"], proforma["igst_amount_inr"]]
        + [proforma[f] for f in copy_fields],
    )
    new_id = cur.lastrowid
    db.execute(
        """INSERT INTO invoice_items (invoice_id, product_id, description, hs_code, boxes,
               net_weight, gross_weight, quantity, unit, unit_price, amount, sort_order)
           SELECT ?, product_id, description, hs_code, boxes, net_weight, gross_weight,
                  quantity, unit, unit_price, amount, sort_order
           FROM invoice_items WHERE invoice_id = ?""",
        (new_id, invoice_id),
    )
    db.commit()
    flash(f"Commercial invoice {invoice_no} created from proforma {proforma['invoice_no']}.", "success")
    return redirect(url_for("invoices.view", invoice_id=new_id))


def _print_context(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        return None
    buyer = db.execute("SELECT * FROM buyers WHERE id = ?", (invoice["buyer_id"],)).fetchone()
    items = db.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY sort_order", (invoice_id,)
    ).fetchall()
    totals = {
        "boxes": sum(i["boxes"] for i in items),
        "net": sum(i["net_weight"] for i in items),
        "gross": sum(i["gross_weight"] for i in items),
        "qty": sum(i["quantity"] for i in items),
    }
    return {"invoice": invoice, "buyer": buyer, "items": items, "totals": totals,
            "s": get_settings(db)}


@bp.route("/<int:invoice_id>/print/invoice")
def print_invoice(invoice_id):
    context = _print_context(invoice_id)
    if context is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    return render_template("invoices/print_invoice.html", **context)


@bp.route("/<int:invoice_id>/print/packing-list")
def print_packing_list(invoice_id):
    context = _print_context(invoice_id)
    if context is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    return render_template("invoices/print_packing_list.html", **context)


@bp.route("/<int:invoice_id>/payments/add", methods=["POST"])
def add_payment(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    if invoice["invoice_type"] != "COMMERCIAL" or invoice["status"] == "CANCELLED":
        flash("Payments can only be recorded on active commercial invoices.", "error")
        return redirect(url_for("invoices.view", invoice_id=invoice_id))
    amount = parse_float(request.form.get("amount"))
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "error")
        return redirect(url_for("invoices.view", invoice_id=invoice_id))
    fx = parse_float(request.form.get("exchange_rate"), invoice["exchange_rate"]) or invoice["exchange_rate"]
    kind = "ADVANCE" if request.form.get("kind") == "ADVANCE" else "BALANCE"
    db.execute(
        """INSERT INTO payments (invoice_id, payment_date, kind, amount, exchange_rate,
                                 amount_inr, bank_reference, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (invoice_id, request.form.get("payment_date") or date.today().isoformat(), kind,
         amount, fx, round(amount * fx, 2),
         request.form.get("bank_reference", "").strip(), request.form.get("notes", "").strip()),
    )
    db.commit()
    flash("Payment recorded.", "success")
    return redirect(url_for("invoices.view", invoice_id=invoice_id))


@bp.route("/payments/<int:payment_id>/delete", methods=["POST"])
def delete_payment(payment_id):
    db = get_db()
    payment = db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if payment is None:
        flash("Payment not found.", "error")
        return redirect(url_for("invoices.index"))
    db.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    db.commit()
    flash("Payment removed.", "success")
    return redirect(url_for("invoices.view", invoice_id=payment["invoice_id"]))
