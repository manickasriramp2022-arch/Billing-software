"""End-to-end smoke tests covering the main billing workflow."""
import os
import tempfile

import pytest

from billing import create_app
from billing.utils import amount_in_words, fiscal_year, inr, money


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    app = create_app({"TESTING": True, "DATABASE": path})
    with app.test_client() as client:
        yield client
    os.unlink(path)


def _create_buyer(client):
    return client.post("/buyers/new", data={
        "name": "Golden Harbour Seafood Pte Ltd", "address": "12 Fishery Port Rd",
        "city": "Singapore", "country": "Singapore", "contact_person": "Mr. Tan",
        "email": "tan@example.com", "phone": "+65 9000 0000", "currency": "USD",
        "incoterm": "CIF", "port_of_discharge": "Changi Airport, Singapore",
        "payment_terms": "30% advance, balance by TT", "notes": "",
    }, follow_redirects=True)


INVOICE_DATA = {
    "buyer_id": "1", "invoice_date": "2026-07-01", "currency": "USD",
    "exchange_rate": "84.50", "incoterm": "CIF", "payment_terms": "30% advance",
    "port_of_loading": "Chennai, India", "port_of_discharge": "Changi Airport, Singapore",
    "country_of_origin": "India", "final_destination": "Singapore",
    "vessel_flight_no": "SQ 529", "container_no": "AWB 618-1234 5678",
    "shipping_bill_no": "", "shipping_bill_date": "", "lc_reference": "",
    "marks_and_numbers": "LIVE MUD CRAB / KEEP UPRIGHT", "gst_treatment": "LUT",
    "lut_arn": "AD330425000123X", "igst_rate": "", "igst_refund_status": "NA",
    "brc_status": "PENDING", "brc_no": "", "brc_date": "", "notes": "",
    "freight_amount": "450", "insurance_amount": "50",
    "item_product_id[]": ["1", "2"],
    "item_description[]": ["Live Mud Crab (Scylla serrata) — Male XXL (1000 g & above)",
                           "Live Mud Crab (Scylla serrata) — Male XL (750 g - 1000 g)"],
    "item_hs_code[]": ["0306 33 00", "0306 33 00"],
    "item_boxes[]": ["20", "10"],
    "item_net_weight[]": ["400", "200"],
    "item_gross_weight[]": ["480", "240"],
    "item_quantity[]": ["400", "200"],
    "item_unit[]": ["KG", "KG"],
    "item_unit_price[]": ["18.50", "15.00"],
}


def test_full_export_workflow(client):
    # masters
    rv = _create_buyer(client)
    assert "Golden Harbour" in rv.get_data(as_text=True)
    rv = client.get("/products/")
    assert "Male XXL" in rv.get_data(as_text=True)  # seeded catalog

    # proforma invoice: 400*18.50 + 200*15 = 10400 + 450 + 50 = 10900
    rv = client.post("/invoices/new?type=PROFORMA", data=INVOICE_DATA, follow_redirects=True)
    page = rv.get_data(as_text=True)
    assert "PI/2026-27/001" in page
    assert "10,900.00" in page

    # issue, then convert to commercial
    assert client.post("/invoices/1/status", data={"action": "issue"}).status_code == 302
    rv = client.post("/invoices/1/convert", follow_redirects=True)
    page = rv.get_data(as_text=True)
    assert "EXP/2026-27/001" in page

    # converting twice is blocked
    rv = client.post("/invoices/1/convert", follow_redirects=True)
    assert "already exists" in rv.get_data(as_text=True)

    # issue commercial and record an advance + balance payment
    client.post("/invoices/2/status", data={"action": "issue"})
    client.post("/invoices/2/payments/add", data={
        "payment_date": "2026-07-02", "kind": "ADVANCE", "amount": "3270",
        "exchange_rate": "84.10", "bank_reference": "FIRC-001",
    })
    rv = client.get("/invoices/2")
    page = rv.get_data(as_text=True)
    assert "3,270.00" in page and "7,630.00" in page  # paid / balance

    client.post("/invoices/2/payments/add", data={
        "payment_date": "2026-07-20", "kind": "BALANCE", "amount": "7630",
        "exchange_rate": "84.80", "bank_reference": "FIRC-002",
    })
    page = client.get("/invoices/2").get_data(as_text=True)
    assert "Paid" in page

    # print documents render with export fields and amount in words
    page = client.get("/invoices/2/print/invoice").get_data(as_text=True)
    assert "COMMERCIAL INVOICE" in page
    assert "US Dollars Ten Thousand Nine Hundred Only" in page
    assert "EXPORT UNDER LUT" in page
    assert "SQ 529" in page
    page = client.get("/invoices/2/print/packing-list").get_data(as_text=True)
    assert "Packing List" in page and "720" in page  # total gross weight

    # reports
    assert client.get("/reports/outstanding").status_code == 200
    page = client.get("/reports/monthly").get_data(as_text=True)
    assert "2026-07" in page
    page = client.get("/reports/buyer-ledger?buyer_id=1").get_data(as_text=True)
    assert "EXP/2026-27/001" in page and "0.00" in page  # settled ledger
    assert client.get("/reports/compliance").status_code == 200
    assert client.get("/").status_code == 200


def test_igst_and_outstanding(client):
    _create_buyer(client)
    data = dict(INVOICE_DATA)
    data.update({"gst_treatment": "IGST", "igst_rate": "5", "igst_refund_status": "PENDING"})
    client.post("/invoices/new?type=COMMERCIAL", data=data, follow_redirects=True)
    client.post("/invoices/1/status", data={"action": "issue"})

    # IGST on INR value: 10900 * 84.50 = 921050; 5% = 46052.50
    page = client.get("/invoices/1").get_data(as_text=True)
    assert "46,052.50" in page
    page = client.get("/reports/compliance").get_data(as_text=True)
    assert "46,052.50" in page and "Pending" in page

    # appears in outstanding until paid
    page = client.get("/reports/outstanding").get_data(as_text=True)
    assert "EXP/2026-27/001" in page and "10,900.00" in page


def test_payments_blocked_on_proforma(client):
    _create_buyer(client)
    client.post("/invoices/new?type=PROFORMA", data=INVOICE_DATA, follow_redirects=True)
    rv = client.post("/invoices/1/payments/add", data={"amount": "100"}, follow_redirects=True)
    assert "only be recorded on active commercial invoices" in rv.get_data(as_text=True)


def test_draft_delete_and_cancel(client):
    _create_buyer(client)
    client.post("/invoices/new?type=COMMERCIAL", data=INVOICE_DATA, follow_redirects=True)
    rv = client.post("/invoices/1/status", data={"action": "delete"}, follow_redirects=True)
    assert "deleted" in rv.get_data(as_text=True)
    # numbering continues after delete without reusing gaps in MAX(seq)
    client.post("/invoices/new?type=COMMERCIAL", data=INVOICE_DATA, follow_redirects=True)
    page = client.get("/invoices/").get_data(as_text=True)
    assert "EXP/2026-27/001" in page


def test_buyer_with_invoices_is_archived_not_deleted(client):
    _create_buyer(client)
    client.post("/invoices/new?type=COMMERCIAL", data=INVOICE_DATA, follow_redirects=True)
    rv = client.post("/buyers/1/delete", follow_redirects=True)
    assert "archived" in rv.get_data(as_text=True)
    # invoice history is preserved
    assert "EXP/2026-27/001" in client.get("/invoices/").get_data(as_text=True)


def test_utils():
    assert money(1234567.5) == "1,234,567.50"
    assert inr(1234567.5) == "12,34,567.50"
    assert inr(999) == "999.00"
    assert fiscal_year("2026-07-09") == "2026-27"
    assert fiscal_year("2026-02-01") == "2025-26"
    assert amount_in_words(10900, "USD") == "US Dollars Ten Thousand Nine Hundred Only"
    assert amount_in_words(1234.56, "USD") == \
        "US Dollars One Thousand Two Hundred Thirty Four and Cents Fifty Six Only"
    assert amount_in_words(921050, "INR") == "Indian Rupees Nine Lakh Twenty One Thousand Fifty Only"
