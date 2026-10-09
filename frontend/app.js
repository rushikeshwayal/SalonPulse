const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = n => "₹" + Number(n || 0).toLocaleString("en-IN", {maximumFractionDigits: 2});
const date = s => s ? new Date(s).toLocaleDateString("en-IN", {day:"2-digit",month:"short"}) : "—";
const normalizePhone = value => {
  let digits = String(value || "").replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return digits;
};

let data = {};
let selectedCustomerCandidate = null;
let confirmedCustomer = null;
let customerSearchTimer = null;
let customerSearchSequence = 0;

async function api(path, opts = {}) {
  const r = await fetch(path, {headers: {"Content-Type":"application/json"}, ...opts});
  const d = await r.json();
  if (!r.ok) throw Error(d.detail || "Request failed");
  return d;
}
function toast(s) {
  const t = $("#toast");
  t.textContent = s;
  t.style.display = "block";
  setTimeout(() => t.style.display = "none", 4000);
}
async function load() {
  try {
    const [dashboard, branches, barbers, customers, visits, feedback, tasks, insights, messages, serviceCatalog] =
      await Promise.all([
        "/api/dashboard", "/api/branches", "/api/barbers", "/api/customers",
        "/api/visits", "/api/feedback", "/api/recovery-tasks", "/api/insights",
        "/api/messages", "/api/service-catalog"
      ].map(api));
    data = {dashboard, branches, barbers, customers, visits, feedback, tasks, insights, messages, serviceCatalog};
    render();
    populate();
  } catch (e) {
    toast("API error: " + e.message);
  }
}
function render() {
  const d = data.dashboard;
  $("#stats").innerHTML = [
    ["Completed visits", d.total_visits, "Across all branches"],
    ["Service revenue", money(d.revenue), "Demo visit history"],
    ["Average rating", d.average_rating ?? "—", "Out of 5 · " + d.feedback_count + " responses"],
    ["Open recovery tasks", d.open_recovery_tasks, "Issues needing attention"]
  ].map(x => `<article class="stat"><span>${x[0]}</span><strong>${x[1]}</strong><small>${x[2]}</small></article>`).join("");

  $("#feedback").innerHTML = data.feedback.length ? data.feedback.map(f => `
    <div class="item"><div class="rating">${f.rating}/5</div><div class="item-content">
      <strong>${esc(f.customer_name)} · ${esc(f.branch_name.replace("The Gentlemen's Club — ",""))}</strong>
      <p>${esc(f.comment || "No written comment.")}</p>
      <div class="meta">${esc(f.barber_name)} · ${date(f.created_at)} · ${f.recovery_task_id ? "Recovery task #" + f.recovery_task_id : "No task needed"}</div>
    </div></div>`).join("") : '<div class="empty">No feedback yet. Create a visit and record feedback.</div>';

  $("#tasks").innerHTML = data.tasks.length ? data.tasks.map(t => `
    <div class="item"><div class="rating">${t.rating}/5</div><div class="item-content">
      <strong>${esc(t.customer_name)} · ${esc(t.branch_name.replace("The Gentlemen's Club — ",""))}</strong>
      <p>${esc(t.comment || "Follow up to understand the issue.")}</p><div class="meta">${esc(t.barber_name)} · ${esc(t.status)}</div>
      ${t.resolution_note ? `<p>${esc(t.resolution_note)}</p>` : ""}
      <div style="display:flex;gap:6px;margin-top:8px"><select id="task-${t.id}">
        <option value="open" ${t.status==="open"?"selected":""}>Open</option>
        <option value="in_progress" ${t.status==="in_progress"?"selected":""}>In progress</option>
        <option value="resolved" ${t.status==="resolved"?"selected":""}>Resolved</option>
      </select><button onclick="updateTask(${t.id})">Update</button></div>
    </div></div>`).join("") : '<div class="empty">No recovery tasks.</div>';

  const max = Math.max(1, ...data.insights.branches.map(b => b.revenue));
  $("#branches").innerHTML = data.insights.branches.map(b => `
    <div class="branch"><div class="branch-top"><strong>${esc(b.branch_name.replace("The Gentlemen's Club — ",""))}</strong><span>${money(b.revenue)}</span></div>
      <div class="track"><div class="fill" style="width:${b.revenue/max*100}%"></div></div>
      <div class="meta">${b.visits} visits · average rating ${b.average_rating ?? "—"} · ${b.low_rating_count} low ratings</div>
    </div>`).join("");

  $("#visits").innerHTML = `<div class="table-wrap"><table class="table"><thead><tr>
    <th>CUSTOMER / CONTACT</th><th>BRANCH</th><th>SERVICES</th><th>TOTAL</th><th>RATING</th>
    </tr></thead><tbody>${data.visits.slice(0,8).map(v => `
      <tr><td><strong>${esc(v.customer_name)}</strong><br><span class="meta">${esc(v.customer_phone || "Phone not added")} · ${esc(v.customer_location || "Location not added")}</span><br><span class="meta">${date(v.completed_at)}</span></td>
      <td>${esc(v.branch_name.replace("The Gentlemen's Club — ",""))}</td><td>${esc(v.service_name)}</td><td>${money(v.amount)}</td><td>${v.rating ?? "Awaiting"}</td></tr>`).join("")}</tbody></table></div>`;

  $("#messages").innerHTML = data.messages.slice(0,5).map(m => `
    <div class="item"><div class="item-content"><strong>${esc(m.customer_name)} <span class="meta">${esc(m.status.replaceAll("_"," "))}</span></strong>
      <p>${esc(m.message)}</p><div class="meta">${date(m.created_at)} · mock-only, not delivered</div>
    </div></div>`).join("") || '<div class="empty">No messages queued.</div>';
}
function populate() {
  $("#branch").innerHTML = data.branches.map(b => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
  $("#branch").onchange = populateBarbers;
  populateBarbers();
  $("#feedbackVisit").innerHTML = data.visits.filter(v => !v.feedback_received).map(v =>
    `<option value="${v.id}">#${v.id} · ${esc(v.customer_name)} · ${esc(v.service_name)}</option>`).join("");
}
function populateBarbers() {
  const id = Number($("#branch").value);
  $("#barber").innerHTML = data.barbers.filter(b => b.branch_id === id)
    .map(b => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
}
function openVisitDialog() {
  $("#visitForm").reset();
  $("input[name='customer_type'][value='new']").checked = true;
  selectedCustomerCandidate = null;
  confirmedCustomer = null;
  $("#customerSearch").value = "";
  $("#customerSearchResults").innerHTML = '<p class="empty">Enter at least 3 characters to search existing customers.</p>';
  $("#selectedCustomerConfirm").hidden = true;
  $("#newCustomerMatchNotice").hidden = true;
  toggleCustomerType();
  populate();
  $("#serviceRows").innerHTML = "";
  addServiceRow();
  calcTotal();
  $("#visitDialog").showModal();
}
function toggleCustomerType() {
  const type = $("input[name='customer_type']:checked").value;
  const isNew = type === "new";
  $("#newCustomerFields").hidden = !isNew;
  $("#returningCustomerFields").hidden = isNew;
  $("#newCustomerPhone").required = isNew;
  $("#newCustomerName").required = isNew;
  $("#customerSearch").required = !isNew;
  if (isNew) {
    selectedCustomerCandidate = null;
    confirmedCustomer = null;
    $("#selectedCustomerConfirm").hidden = true;
  } else {
    $("#newCustomerMatchNotice").hidden = true;
  }
}
function addServiceRow(seed = {}) {
  if (!data.serviceCatalog?.length) return;
  const row = document.createElement("div");
  row.className = "service-row";
  const serviceOptions = data.serviceCatalog.map(s =>
    `<option value="${esc(s.name)}" data-price="${Number(s.default_price)}" ${seed.service_name === s.name ? "selected" : ""}>${esc(s.name)}</option>`
  ).join("");
  const initial = data.serviceCatalog.find(s => s.name === seed.service_name) || data.serviceCatalog[0];
  row.innerHTML = `
    <label class="service-name"><span class="mobile-label">Service</span><select class="service-select" required>${serviceOptions}</select></label>
    <label class="service-qty"><span class="mobile-label">Qty</span><input class="qty-input" type="number" min="1" max="50" step="1" value="${seed.quantity || 1}" required></label>
    <label class="service-price"><span class="mobile-label">Price (₹)</span><input class="price-input" type="number" min="0" max="100000" step="0.01" value="${seed.unit_price ?? initial.default_price}" required></label>
    <button type="button" class="remove-service" aria-label="Remove service" title="Remove service">×</button>`;
  row.querySelector(".service-select").addEventListener("change", e => {
    const chosen = data.serviceCatalog.find(s => s.name === e.target.value);
    if (chosen) row.querySelector(".price-input").value = chosen.default_price;
    calcTotal();
  });
  row.querySelectorAll("input").forEach(el => el.addEventListener("input", calcTotal));
  row.querySelector(".remove-service").addEventListener("click", () => {
    if ($("#serviceRows").children.length === 1) {
      toast("Keep at least one service on the visit.");
      return;
    }
    row.remove();
    calcTotal();
  });
  $("#serviceRows").appendChild(row);
  calcTotal();
}
function readServices() {
  return [...$("#serviceRows").querySelectorAll(".service-row")].map(row => ({
    service_name: row.querySelector(".service-select").value,
    quantity: Number(row.querySelector(".qty-input").value),
    unit_price: Number(row.querySelector(".price-input").value)
  }));
}
function calcTotal() {
  const total = readServices().reduce((sum, s) => sum + (s.quantity || 0) * (s.unit_price || 0), 0);
  $("#visitTotal").textContent = money(total);
}
function renderCustomerResults(matches, term) {
  const box = $("#customerSearchResults");
  if (!matches.length) {
    box.innerHTML = `<p class="empty">No customer found for “${esc(term)}”. If they're new, switch to New customer.</p>`;
    return;
  }
  box.innerHTML = matches.map(c => `
    <article class="customer-result"><div><strong>${esc(c.name)}</strong><div class="meta">${esc(c.phone || "No phone saved")} · ${esc(c.location || "Location not added")}</div>
      <div class="meta">${c.visit_count} previous visit${c.visit_count===1?"":"s"}${c.last_visit ? " · Last visit " + date(c.last_visit) : ""}</div></div>
      <button type="button" class="secondary" data-review-customer="${c.id}">Review</button></article>`).join("");
}
async function searchReturningCustomer() {
  const term = $("#customerSearch").value.trim();
  const requestId = ++customerSearchSequence;
  selectedCustomerCandidate = null;
  confirmedCustomer = null;
  $("#selectedCustomerConfirm").hidden = true;
  if (term.length < 3) {
    $("#customerSearchResults").innerHTML = '<p class="empty">Enter at least 3 characters to search existing customers.</p>';
    return;
  }
  $("#customerSearchResults").innerHTML = '<p class="empty">Searching customers…</p>';
  try {
    const matches = await api("/api/customers/search?q=" + encodeURIComponent(term));
    if (requestId !== customerSearchSequence) return;
    renderCustomerResults(matches, term);
  } catch (e) {
    if (requestId === customerSearchSequence) $("#customerSearchResults").innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}
async function checkNewCustomerPhone() {
  const phone = $("#newCustomerPhone").value.trim();
  if (normalizePhone(phone).length < 7) {
    $("#newCustomerMatchNotice").hidden = true;
    return;
  }
  try {
    const matches = await api("/api/customers/search?q=" + encodeURIComponent(phone));
    const digits = normalizePhone(phone);
    const found = matches.find(c => normalizePhone(c.phone) === digits);
    if (!found) {
      $("#newCustomerMatchNotice").hidden = true;
      return;
    }
    selectedCustomerCandidate = found;
    const notice = $("#newCustomerMatchNotice");
    notice.innerHTML = `This number is already saved for <strong>${esc(found.name)}</strong>. <button type="button" class="text-action" data-use-existing="${found.id}">Use existing customer</button>`;
    notice.hidden = false;
  } catch (e) {
    toast("Couldn't check that number: " + e.message);
  }
}
function reviewCustomer(id) {
  const candidate = data.customers.find(c => c.id === id) ||
    window.lastCustomerSearchMatches?.find(c => c.id === id) || selectedCustomerCandidate;
  // Search result details may include customers not in the initial dashboard data.
  if (!candidate || candidate.id !== id) {
    searchReturningCustomer();
    return;
  }
  selectedCustomerCandidate = candidate;
  confirmedCustomer = null;
  const card = $("#selectedCustomerConfirm");
  card.innerHTML = `<div class="selected-customer-title">Confirm customer details</div>
    <strong>${esc(candidate.name)}</strong>
    <div class="meta">Phone: ${esc(candidate.phone || "Not saved")} · Location: ${esc(candidate.location || "Not added")}</div>
    <div class="meta">${candidate.visit_count} previous visit${candidate.visit_count===1?"":"s"}</div>
    <div class="confirm-actions"><button type="button" class="primary" data-confirm-customer="${candidate.id}">Yes, use this customer</button><button type="button" class="secondary" data-change-customer>Choose another</button></div>`;
  card.hidden = false;
}
function useExistingCustomer(id) {
  const radio = $("input[name='customer_type'][value='returning']");
  radio.checked = true;
  toggleCustomerType();
  const candidate = selectedCustomerCandidate?.id === id ? selectedCustomerCandidate :
    data.customers.find(c => c.id === id);
  $("#customerSearch").value = candidate?.phone || $("#newCustomerPhone").value.trim();
  searchReturningCustomer();
}
$("#newVisit").onclick = openVisitDialog;
$("#newFeedback").onclick = () => {
  populate();
  if (!$("#feedbackVisit").options.length) {
    toast("Create a new visit first; all current visits already have feedback.");
    return;
  }
  $("#feedbackDialog").showModal();
};
document.querySelectorAll(".close").forEach(b => b.onclick = () => b.closest("dialog").close());
document.querySelectorAll("input[name='customer_type']").forEach(r => r.addEventListener("change", toggleCustomerType));
$("#addService").addEventListener("click", () => {
  if ($("#serviceRows").children.length >= 10) {
    toast("A visit can have up to 10 service lines.");
    return;
  }
  addServiceRow();
});
$("#customerSearch").addEventListener("input", () => {
  clearTimeout(customerSearchTimer);
  customerSearchTimer = setTimeout(searchReturningCustomer, 250);
});
$("#customerSearchResults").addEventListener("click", async e => {
  const btn = e.target.closest("[data-review-customer]");
  if (!btn) return;
  const id = Number(btn.dataset.reviewCustomer);
  const searchTerm = $("#customerSearch").value.trim();
  try {
    const matches = await api("/api/customers/search?q=" + encodeURIComponent(searchTerm));
    const candidate = matches.find(c => c.id === id);
    if (!candidate) return toast("Customer result is no longer available. Search again.");
    selectedCustomerCandidate = candidate;
    reviewCustomer(id);
  } catch (err) { toast(err.message); }
});
$("#selectedCustomerConfirm").addEventListener("click", e => {
  const yes = e.target.closest("[data-confirm-customer]");
  if (yes) {
    if (!selectedCustomerCandidate || selectedCustomerCandidate.id !== Number(yes.dataset.confirmCustomer)) return;
    confirmedCustomer = selectedCustomerCandidate;
    const c = confirmedCustomer;
    $("#selectedCustomerConfirm").innerHTML = `<div class="confirmed-banner">✓ Customer confirmed</div><strong>${esc(c.name)}</strong>
      <div class="meta">${esc(c.phone || "No phone saved")} · ${esc(c.location || "Location not added")}</div>
      <button type="button" class="text-action" data-change-customer>Change customer</button>`;
    toast("Returning customer confirmed.");
  }
  if (e.target.closest("[data-change-customer]")) {
    confirmedCustomer = null;
    selectedCustomerCandidate = null;
    $("#selectedCustomerConfirm").hidden = true;
    $("#customerSearch").focus();
    searchReturningCustomer();
  }
});
$("#newCustomerMatchNotice").addEventListener("click", e => {
  const b = e.target.closest("[data-use-existing]");
  if (b) useExistingCustomer(Number(b.dataset.useExisting));
});
$("#newCustomerPhone").addEventListener("blur", checkNewCustomerPhone);

$("#visitForm").onsubmit = async e => {
  e.preventDefault();
  const type = $("input[name='customer_type']:checked").value;
  const services = readServices();
  if (!services.length || services.some(s => !s.service_name || !Number.isInteger(s.quantity) || s.quantity < 1 || !Number.isFinite(s.unit_price) || s.unit_price < 0)) {
    toast("Check each service, quantity, and price.");
    return;
  }
  const payload = {
    branch_id: Number($("#branch").value),
    barber_id: Number($("#barber").value),
    services,
    messaging_consent: $("input[name='messaging_consent']").checked
  };
  if (type === "returning") {
    if (!confirmedCustomer) {
      toast("Please review and confirm the returning customer's details first.");
      return;
    }
    payload.customer_id = confirmedCustomer.id;
  } else {
    payload.customer_name = $("#newCustomerName").value.trim();
    payload.customer_phone = $("#newCustomerPhone").value.trim();
    payload.customer_location = $("#newCustomerLocation").value.trim();
    if (!payload.customer_name || !payload.customer_phone) {
      toast("Customer name and phone number are required.");
      return;
    }
  }
  const save = $("#saveVisit");
  save.disabled = true;
  save.textContent = "Saving…";
  try {
    const r = await api("/api/visits", {method:"POST", body:JSON.stringify(payload)});
    $("#visitDialog").close();
    await load();
    toast(`Visit #${r.visit.id} saved · Total ${money(r.visit.amount)}. ${r.notice}`);
  } catch (err) {
    toast(err.message);
  } finally {
    save.disabled = false;
    save.textContent = "Save visit";
  }
};
$("#feedbackForm").onsubmit = async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    const r = await api("/api/feedback", {method:"POST",body:JSON.stringify({
      visit_id:+f.get("visit_id"), rating:+f.get("rating"), comment:f.get("comment")
    })});
    $("#feedbackDialog").close();
    await load();
    toast(r.recovery_created ? "Feedback saved; a manager recovery task was created." : "Feedback saved.");
  } catch(err) { toast(err.message); }
};
async function updateTask(id) {
  const status = $("#task-" + id).value;
  const old = data.tasks.find(t => t.id === id);
  let note = old.resolution_note;
  if (status === "resolved" && !note) note = prompt("What action resolved the issue?") || "Marked resolved in demo";
  try {
    await api("/api/recovery-tasks/" + id,{method:"PATCH",body:JSON.stringify({status,resolution_note:note})});
    await load();
    toast("Recovery task updated");
  } catch(e) { toast(e.message); }
}
window.updateTask = updateTask;
$("#reset").onclick = async () => {
  if (!confirm("Reset all demo data to the fictional sample? This removes records added in this demo.")) return;
  try {
    await api("/api/demo/reset",{method:"POST"});
    await load();
    toast("Demo data reset");
  } catch(e) { toast(e.message); }
};
load();
