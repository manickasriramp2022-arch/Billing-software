# 🦀 Export Billing — Mud Crab Export Billing Software

Billing and export-documentation software for a live mud crab export business.
Built with Python (Flask) and SQLite — a single, self-contained web app with no
external services required.

## Features

- **Buyer master** — overseas buyer details, invoicing currency, default
  Incoterm (FOB/CIF/CFR/…), default port of discharge and payment terms.
- **Product catalog** — mud crab grades and size ranges, packing unit, HS code,
  billing unit and default rate. Seeded with common live mud crab
  (*Scylla serrata*) grades on first run; fully editable.
- **Invoices** — proforma and commercial invoices with line items, freight and
  insurance, automatic fiscal-year numbering (`PI/2026-27/001`,
  `EXP/2026-27/001`), draft → issued → cancelled lifecycle, and one-click
  **convert proforma → commercial**.
- **Print documents** — A4 print-ready **commercial invoice** (with amount in
  words, LUT/IGST declaration, bank details, declaration and signature block)
  and **packing list** (boxes, net/gross weight). Use the browser's
  *Print → Save as PDF*.
- **Export documentation fields** — shipping bill number and date, port of
  loading/discharge, vessel/flight number, container/AWB number, LC reference,
  marks & numbers, country of origin/final destination.
- **Currency handling** — invoice in USD or other foreign currency with an
  exchange rate to INR; INR equivalents shown throughout and on reports;
  Indian-style ₹ grouping (12,34,567.00).
- **GST / compliance** — per-invoice GST treatment: export **under LUT**
  (zero-rated, LUT ARN printed on the invoice) or **with IGST payment**
  (IGST computed on the INR value, refund status tracked
  Pending → Filed → Received).
- **Payment tracking** — advance and balance payments per commercial invoice
  with realized exchange rate and bank/FIRC reference; **BRC/eBRC status**
  (pending/realized, number and date) per invoice.
- **Reports** — outstanding receivables with ageing, monthly export summary
  (boxes, quantity, value by currency and INR), buyer-wise ledger with running
  balance, and a BRC + IGST refund compliance tracker.

## Running it

```bash
pip install -r requirements.txt
python run.py
```

Open <http://localhost:5000>. The SQLite database is created automatically at
`instance/billing.sqlite` (set `BILLING_DB=/path/to/file.sqlite` to override).

First steps:

1. **Settings** — enter the exporter's name, address, GSTIN, IEC, LUT ARN and
   bank details (these print on the documents).
2. **Buyers** — add overseas buyers.
3. **Products** — review the seeded grade list, adjust sizes/rates/HS code.
4. Create a **proforma**, collect the advance, then **convert to commercial**
   at shipment and fill in the shipping bill / vessel / container details.

For deployment on a LAN or server, run it behind a production WSGI server,
e.g. `pip install waitress` then
`waitress-serve --host 0.0.0.0 --port 5000 run:app`, and set a real
`SECRET_KEY` environment variable.

## Tests

```bash
pip install pytest
python -m pytest tests/
```

## Notes for the accountant

- The seeded HS code is `0306 33 00` (crabs, live/fresh/chilled). Confirm the
  exact 8-digit ITC-HS code with your CHA before filing.
- IGST on export-with-payment invoices is computed on the INR value at the
  invoice exchange rate; verify against the shipping bill values when claiming
  refunds.
- Outstanding receivables older than 90 days are highlighted — FEMA requires
  export proceeds to be realized within 9 months.
