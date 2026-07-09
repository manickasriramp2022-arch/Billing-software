// Invoice editor: dynamic item rows, live totals, buyer/product defaults.
(function () {
  const form = document.getElementById("invoice-form");
  if (!form) return;

  const body = document.getElementById("items-body");
  const template = document.getElementById("row-template");
  const fmt = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const num = (el) => parseFloat(el && el.value ? el.value : 0) || 0;

  function recalc() {
    let subtotal = 0;
    body.querySelectorAll(".item-row").forEach((row) => {
      const amount = num(row.querySelector(".item-qty")) * num(row.querySelector(".item-price"));
      row.querySelector(".item-amount").textContent = fmt(amount);
      subtotal += amount;
    });
    const total = subtotal + num(document.getElementById("freight")) + num(document.getElementById("insurance"));
    const fx = num(document.getElementById("fx-rate"));
    document.getElementById("t-subtotal").textContent = fmt(subtotal);
    document.getElementById("t-total").textContent = fmt(total);
    document.getElementById("t-currency").textContent = document.getElementById("currency-select").value;
    document.getElementById("t-inr").textContent = fx ? "₹ " + fmt(total * fx) : "— (set exchange rate)";
  }

  function wireRow(row) {
    row.querySelector(".item-product").addEventListener("change", (e) => {
      const opt = e.target.selectedOptions[0];
      if (!opt || !opt.value) return;
      const set = (selector, value) => {
        const el = row.querySelector(selector);
        if (el && !el.value) el.value = value;
      };
      const descEl = row.querySelector(".item-description");
      if (!descEl.value) descEl.value = opt.dataset.description || "";
      set(".item-hs", opt.dataset.hs);
      set(".item-unit", opt.dataset.unit);
      if (parseFloat(opt.dataset.rate) > 0) set(".item-price", opt.dataset.rate);
      recalc();
    });
    row.querySelector(".remove-row").addEventListener("click", () => {
      if (body.querySelectorAll(".item-row").length > 1) row.remove();
      else row.querySelectorAll("input").forEach((i) => (i.value = ""));
      recalc();
    });
    // billed qty defaults to net weight for live crab sold per kg
    const netEl = row.querySelector('input[name="item_net_weight[]"]');
    const qtyEl = row.querySelector(".item-qty");
    netEl.addEventListener("change", () => {
      if (!qtyEl.value) { qtyEl.value = netEl.value; recalc(); }
    });
  }

  document.getElementById("add-row").addEventListener("click", () => {
    const clone = template.content.querySelector("tr").cloneNode(true);
    body.appendChild(clone);
    wireRow(clone);
  });

  const buyerSelect = document.getElementById("buyer-select");
  buyerSelect.addEventListener("change", () => {
    const opt = buyerSelect.selectedOptions[0];
    if (!opt || !opt.value) return;
    const apply = (id, value) => {
      const el = document.getElementById(id);
      if (el && value && !el.value) el.value = value;
    };
    if (opt.dataset.currency) document.getElementById("currency-select").value = opt.dataset.currency;
    if (opt.dataset.incoterm) document.getElementById("incoterm-select").value = opt.dataset.incoterm;
    apply("payment-terms", opt.dataset.terms);
    apply("pod-input", opt.dataset.pod);
    apply("dest-input", opt.dataset.country);
    recalc();
  });

  function toggleIgst() {
    const isIgst = document.getElementById("gst-treatment").value === "IGST";
    document.querySelectorAll(".igst-only").forEach((el) => (el.style.display = isIgst ? "" : "none"));
  }
  document.getElementById("gst-treatment").addEventListener("change", toggleIgst);

  form.addEventListener("input", recalc);
  body.querySelectorAll(".item-row").forEach(wireRow);
  toggleIgst();
  recalc();
})();
