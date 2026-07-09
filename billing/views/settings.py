from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..db import DEFAULT_SETTINGS, get_db, get_settings

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
def edit():
    db = get_db()
    if request.method == "POST":
        for key in DEFAULT_SETTINGS:
            if key in request.form:
                db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)"
                    " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, request.form[key].strip()),
                )
        db.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings.edit"))
    return render_template("settings/form.html", s=get_settings(db))
