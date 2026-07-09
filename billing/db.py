import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DEFAULT_SETTINGS = {
    "company_name": "Your Company Name",
    "company_address": "Address line 1\nAddress line 2\nTamil Nadu, India",
    "company_email": "",
    "company_phone": "",
    "company_gstin": "",
    "company_iec": "",
    "lut_arn": "",
    "bank_beneficiary": "",
    "bank_name": "",
    "bank_account": "",
    "bank_swift": "",
    "bank_ifsc": "",
    "bank_address": "",
    "default_port_of_loading": "Chennai, India",
    "default_hs_code": "0306 33 00",
    "prefix_commercial": "EXP",
    "prefix_proforma": "PI",
    "invoice_footer_note": "Live mud crab (Scylla serrata) of Indian origin. "
                           "Supply meant for export. Subject to Indian jurisdiction.",
}

# Seed catalog for a typical Indian live mud crab exporter; fully editable afterwards.
SEED_PRODUCTS = [
    ("Live Mud Crab (Scylla serrata)", "Male XXL", "1000 g & above", "Styrofoam box"),
    ("Live Mud Crab (Scylla serrata)", "Male XL", "750 g - 1000 g", "Styrofoam box"),
    ("Live Mud Crab (Scylla serrata)", "Male L", "500 g - 750 g", "Styrofoam box"),
    ("Live Mud Crab (Scylla serrata)", "Male M", "350 g - 500 g", "Styrofoam box"),
    ("Live Mud Crab (Scylla serrata)", "Female F1", "500 g & above", "Styrofoam box"),
    ("Live Mud Crab (Scylla serrata)", "Female F2", "350 g - 500 g", "Styrofoam box"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Create the schema and seed defaults on first run. Safe to call repeatedly."""
    db = sqlite3.connect(app.config["DATABASE"])
    try:
        db.executescript(SCHEMA_PATH.read_text())
        for key, value in DEFAULT_SETTINGS.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            hs = DEFAULT_SETTINGS["default_hs_code"]
            for name, grade, size_range, packing in SEED_PRODUCTS:
                db.execute(
                    "INSERT INTO products (name, grade, size_range, packing_unit, hs_code, unit)"
                    " VALUES (?, ?, ?, ?, ?, 'KG')",
                    (name, grade, size_range, packing, hs),
                )
        db.commit()
    finally:
        db.close()


def get_settings(db=None):
    db = db or get_db()
    return {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM settings")}


def init_app(app):
    app.teardown_appcontext(close_db)
    init_db(app)
