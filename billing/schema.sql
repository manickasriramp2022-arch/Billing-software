PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS buyers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    address        TEXT NOT NULL DEFAULT '',
    city           TEXT NOT NULL DEFAULT '',
    country        TEXT NOT NULL DEFAULT '',
    contact_person TEXT NOT NULL DEFAULT '',
    email          TEXT NOT NULL DEFAULT '',
    phone          TEXT NOT NULL DEFAULT '',
    currency       TEXT NOT NULL DEFAULT 'USD',
    incoterm       TEXT NOT NULL DEFAULT 'FOB',
    port_of_discharge TEXT NOT NULL DEFAULT '',
    payment_terms  TEXT NOT NULL DEFAULT '',
    notes          TEXT NOT NULL DEFAULT '',
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    grade        TEXT NOT NULL DEFAULT '',
    size_range   TEXT NOT NULL DEFAULT '',
    packing_unit TEXT NOT NULL DEFAULT '',
    hs_code      TEXT NOT NULL DEFAULT '',
    unit         TEXT NOT NULL DEFAULT 'KG',
    default_rate REAL NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_type   TEXT NOT NULL CHECK (invoice_type IN ('PROFORMA', 'COMMERCIAL')),
    invoice_no     TEXT NOT NULL UNIQUE,
    fy             TEXT NOT NULL,               -- fiscal year label e.g. 2026-27
    seq            INTEGER NOT NULL,            -- numeric part of invoice_no within fy+type
    status         TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'ISSUED', 'CANCELLED')),
    buyer_id       INTEGER NOT NULL REFERENCES buyers(id),
    invoice_date   TEXT NOT NULL,
    currency       TEXT NOT NULL DEFAULT 'USD',
    exchange_rate  REAL NOT NULL DEFAULT 1,     -- 1 unit of currency in INR
    incoterm       TEXT NOT NULL DEFAULT 'FOB',
    payment_terms  TEXT NOT NULL DEFAULT '',
    -- export documentation
    port_of_loading    TEXT NOT NULL DEFAULT '',
    port_of_discharge  TEXT NOT NULL DEFAULT '',
    country_of_origin  TEXT NOT NULL DEFAULT 'India',
    final_destination  TEXT NOT NULL DEFAULT '',
    vessel_flight_no   TEXT NOT NULL DEFAULT '',
    container_no       TEXT NOT NULL DEFAULT '',
    shipping_bill_no   TEXT NOT NULL DEFAULT '',
    shipping_bill_date TEXT NOT NULL DEFAULT '',
    lc_reference       TEXT NOT NULL DEFAULT '',
    marks_and_numbers  TEXT NOT NULL DEFAULT '',
    -- GST / compliance
    gst_treatment      TEXT NOT NULL DEFAULT 'LUT' CHECK (gst_treatment IN ('LUT', 'IGST')),
    lut_arn            TEXT NOT NULL DEFAULT '',
    igst_rate          REAL NOT NULL DEFAULT 0,
    igst_amount_inr    REAL NOT NULL DEFAULT 0,
    igst_refund_status TEXT NOT NULL DEFAULT 'NA' CHECK (igst_refund_status IN ('NA', 'PENDING', 'FILED', 'RECEIVED')),
    -- bank realization certificate
    brc_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (brc_status IN ('PENDING', 'REALIZED')),
    brc_no     TEXT NOT NULL DEFAULT '',
    brc_date   TEXT NOT NULL DEFAULT '',
    -- money (denormalised totals, recomputed on every save)
    subtotal         REAL NOT NULL DEFAULT 0,
    freight_amount   REAL NOT NULL DEFAULT 0,
    insurance_amount REAL NOT NULL DEFAULT 0,
    total            REAL NOT NULL DEFAULT 0,
    total_inr        REAL NOT NULL DEFAULT 0,
    notes        TEXT NOT NULL DEFAULT '',
    proforma_id  INTEGER REFERENCES invoices(id),  -- commercial invoice's source proforma
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id  INTEGER REFERENCES products(id),
    description TEXT NOT NULL DEFAULT '',
    hs_code     TEXT NOT NULL DEFAULT '',
    boxes       REAL NOT NULL DEFAULT 0,
    net_weight  REAL NOT NULL DEFAULT 0,   -- kg, for packing list
    gross_weight REAL NOT NULL DEFAULT 0,  -- kg, for packing list
    quantity    REAL NOT NULL DEFAULT 0,   -- billed quantity
    unit        TEXT NOT NULL DEFAULT 'KG',
    unit_price  REAL NOT NULL DEFAULT 0,
    amount      REAL NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payment_date  TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'BALANCE' CHECK (kind IN ('ADVANCE', 'BALANCE')),
    amount        REAL NOT NULL DEFAULT 0,   -- in invoice currency
    exchange_rate REAL NOT NULL DEFAULT 1,   -- realized rate to INR
    amount_inr    REAL NOT NULL DEFAULT 0,
    bank_reference TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_invoices_buyer ON invoices(buyer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_type_fy ON invoices(invoice_type, fy);
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
