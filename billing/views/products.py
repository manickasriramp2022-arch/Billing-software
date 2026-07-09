from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..db import get_db, get_settings
from ..utils import parse_float

bp = Blueprint("products", __name__, url_prefix="/products")

FIELDS = ["name", "grade", "size_range", "packing_unit", "hs_code", "unit", "default_rate"]


def _form_values():
    values = {f: request.form.get(f, "").strip() for f in FIELDS}
    values["unit"] = values["unit"] or "KG"
    values["hs_code"] = values["hs_code"] or get_settings().get("default_hs_code", "")
    values["default_rate"] = parse_float(values["default_rate"])
    return values


@bp.route("/")
def index():
    rows = get_db().execute(
        "SELECT * FROM products WHERE active = 1 ORDER BY name, grade"
    ).fetchall()
    return render_template("products/list.html", products=rows)


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        values = _form_values()
        if not values["name"]:
            flash("Product name is required.", "error")
        else:
            db = get_db()
            db.execute(
                f"INSERT INTO products ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                [values[f] for f in FIELDS],
            )
            db.commit()
            flash("Product added.", "success")
            return redirect(url_for("products.index"))
    return render_template("products/form.html", product=None,
                           default_hs=get_settings().get("default_hs_code", ""))


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
def edit(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        flash("Product not found.", "error")
        return redirect(url_for("products.index"))
    if request.method == "POST":
        values = _form_values()
        if not values["name"]:
            flash("Product name is required.", "error")
        else:
            db.execute(
                "UPDATE products SET " + ", ".join(f"{f} = ?" for f in FIELDS) + " WHERE id = ?",
                [values[f] for f in FIELDS] + [product_id],
            )
            db.commit()
            flash("Product updated.", "success")
            return redirect(url_for("products.index"))
    return render_template("products/form.html", product=product,
                           default_hs=get_settings().get("default_hs_code", ""))


@bp.route("/<int:product_id>/delete", methods=["POST"])
def delete(product_id):
    db = get_db()
    used = db.execute("SELECT COUNT(*) FROM invoice_items WHERE product_id = ?", (product_id,)).fetchone()[0]
    if used:
        db.execute("UPDATE products SET active = 0 WHERE id = ?", (product_id,))
        flash("Product is used on invoices, so it was archived instead of deleted.", "success")
    else:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        flash("Product deleted.", "success")
    db.commit()
    return redirect(url_for("products.index"))
