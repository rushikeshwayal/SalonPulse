const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = n => "₹" + Number(n || 0).toLocaleString("en-IN", {maximumFractionDigits: 2});
const date = s => s ? new Date(s).toLocaleDateString("en-IN", {day:"2-digit",month:"short"}) : "—";
const dateTime = s => s ? new Date(s).toLocaleString("en-IN", {day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}) : "—";
const localDateTimeValue = d => {
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};
const normalizePhone = value => {
  let digits = String(value || "").replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return digits;
};

let data = {};
let authUser = null;
let editingVisitId = null;
let activeBarberView = "overview";
let expandedVisitsLoaded = false;
let expandedFeedbackLoaded = false;
let expandedAuditLoaded = false;
let selectedCustomerCandidate = null;
let confirmedCustomer = null;
let customerSearchTimer = null;
let customerSearchSequence = 0;
let lastCustomerSearchMatches = [];

async function api(path, opts = {}) {
  const headers = new Headers(opts.headers || {});
  if (opts.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = sessionStorage.getItem("salonpulse_token");
  if (token && path !== "/api/auth/login") headers.set("Authorization", "Bearer " + token);
  const response = await fetch(path, {...opts, headers});
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.detail || "Request failed (" + response.status + ")");
    error.status = response.status;
    if (response.status === 401 && path !== "/api/auth/login") {
      sessionStorage.removeItem("salonpulse_token");
      showLogin();
    }
    throw error;
  }
  return result;
}
function toast(s) {
  const t = $("#toast");
  t.textContent = s;
  t.style.display = "block";
  setTimeout(() => t.style.display = "none", 4000);
}

function showLogin(message = "") {
  authUser = null;
  $("#appShell").hidden = true;
  $("#loginScreen").hidden = false;
  $("#passwordChangeScreen").hidden = true;
  $("#loginError").hidden = !message;
  $("#loginError").textContent = message;
  $("#loginPassword").value = "";
}
function showPasswordChange() {
  $("#appShell").hidden = true;
  $("#loginScreen").hidden = true;
  $("#passwordChangeScreen").hidden = false;
  $("#passwordChangeError").hidden = true;
}
function setBarberView(view) {
  activeBarberView = view;
  document.querySelectorAll("[data-barber-tab]").forEach(button => {
    const selected = button.dataset.barberTab === view;
    button.classList.toggle("active", selected);
    if (selected) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
    if (selected && window.matchMedia("(max-width: 760px)").matches) {
      button.scrollIntoView({behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", inline: "center", block: "nearest"});
    }
  });
  const barberMode = authUser?.role === "barber";
  document.querySelectorAll("[data-barber-view]").forEach(section => {
    section.hidden = barberMode
      ? section.dataset.barberView !== view
      : section.hasAttribute("data-barber-only");
  });
}
function applyRoleUi(user) {
  authUser = user;
  $("#loginScreen").hidden = true;
  $("#passwordChangeScreen").hidden = true;
  $("#appShell").hidden = false;
  const displayName = user.display_name || user.username || user.email || "SalonPulse user";
  const initials = displayName.trim().split(/\\s+/).slice(0, 2).map(part => part.charAt(0)).join("").toUpperCase() || "U";
  const owner = user.role === "owner";
  $("#currentUser").textContent = displayName;
  $("#currentRole").textContent = owner ? "OWNER WORKSPACE" : "BARBER WORKSPACE";
  $("#profileInitials").textContent = initials;
  $("#profileAvatar").textContent = initials;
  $("#profileDisplayName").textContent = displayName;
  $("#profileEmailHeadline").textContent = user.email || "Email not provided";
  $("#profileEmail").textContent = user.email || "Not provided";
  $("#profileUsername").textContent = user.username || "Not provided";
  $("#profileWorkspace").textContent = owner ? "Owner · Business-wide access" : "Barber · Personal workspace";
  const assignedBranch = !owner && data.branches?.length ? data.branches[0] : null;
  $("#profileBranchRow").hidden = owner;
  $("#profileBranch").textContent = assignedBranch
    ? assignedBranch.name.replace("The Gentlemen's Club — ", "") + (assignedBranch.location ? " · " + assignedBranch.location : "")
    : "Not assigned";
  document.body.classList.toggle("barber-mode", !owner);
  document.querySelectorAll("[data-owner-only]").forEach(el => { el.hidden = !owner; });
  document.querySelectorAll("[data-barber-only]").forEach(el => { el.hidden = owner; });
  $("#workspaceEyebrow").textContent = owner ? "OWNER OVERVIEW" : "BARBER WORKSPACE";
  $("#workspaceTitle").innerHTML = owner ? "Your business,<br>at a glance." : "Every visit.<br>Every detail.";
  $("#workspaceSubtitle").textContent = owner
    ? "Branch performance, employee results, revenue and guest recovery in one place."
    : "Your assigned visits, customer history and a clear record of every change.";
  $("#visitListTitle").textContent = owner ? "Recent visits across all stores" : "Your visits";
  $("#visitListSubtitle").textContent = owner
    ? "Edit a visit or inspect the full version history."
    : "Select a record to see the full details and its saved versions.";
  setBarberView(owner ? "overview" : activeBarberView);
}
document.querySelectorAll("[data-barber-tab]").forEach(button => {
  button.addEventListener("click", async () => {
    const view = button.dataset.barberTab;
    setBarberView(view);
    try {
      if (view === "visits" && !expandedVisitsLoaded) {
        data.visits = await api("/api/visits?limit=100");
        expandedVisitsLoaded = true;
        render();
        populate();
      } else if (view === "feedback" && !expandedFeedbackLoaded) {
        data.feedback = await api("/api/feedback?limit=100");
        expandedFeedbackLoaded = true;
        render();
      } else if (view === "activity" && !expandedAuditLoaded) {
        data.auditLogs = await api("/api/audit-logs?limit=100");
        expandedAuditLoaded = true;
        render();
      }
    } catch (err) {
      toast("Couldn't load this section: " + err.message);
    }
  });
});
async function initAuth() {
  if (!sessionStorage.getItem("salonpulse_token")) {
    showLogin();
    return;
  }
  try {
    const user = await api("/api/auth/me");
    if (user.must_change_password) {
      showPasswordChange();
      return;
    }
    await load();
  } catch (e) {
    showLogin(e.status === 401 ? "" : e.message);
  }
}
$("#loginForm").onsubmit = async e => {
  e.preventDefault();
  const submit = $("#loginButton");
  const form = new FormData(e.target);
  const error = $("#loginError");
  error.hidden = true;
  submit.disabled = true;
  submit.textContent = "Signing in…";
  try {
    const result = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        identifier: String(form.get("identifier") || "").trim(),
        password: String(form.get("password") || "")
      })
    });
    sessionStorage.setItem("salonpulse_token", result.access_token);
    if (result.user.must_change_password) showPasswordChange();
    else await load();
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
    submit.innerHTML = 'Sign in <span>→</span>';
  }
};
$("#passwordChangeForm").onsubmit = async e => {
  e.preventDefault();
  const form = new FormData(e.target);
  const next = String(form.get("new_password") || "");
  const confirm = $("#confirmPassword").value;
  const error = $("#passwordChangeError");
  if (next !== confirm) {
    error.textContent = "The new passwords do not match.";
    error.hidden = false;
    return;
  }
  const button = $("#changePasswordButton");
  button.disabled = true;
  button.textContent = "Saving…";
  error.hidden = true;
  try {
    await api("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: String(form.get("current_password") || ""),
        new_password: next
      })
    });
    e.target.reset();
    toast("Password updated. Welcome to SalonPulse.");
    await load();
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Save new password <span>→</span>';
  }
};
function signOut() {
  sessionStorage.removeItem("salonpulse_token");
  $("#loginForm").reset();
  $("#passwordChangeForm").reset();
  showLogin();
}
$("#profileButton").addEventListener("click", () => {
  if (!$("#profileDialog").open) $("#profileDialog").showModal();
});
$("#profileSignOut").addEventListener("click", () => {
  $("#profileDialog").close();
  signOut();
});
$("#cancelPasswordChange").addEventListener("click", signOut);
async function load() {
  try {
    const payload = await api("/api/bootstrap");
    data = payload;
    authUser = payload.user;
    applyRoleUi(authUser);
    render();
    populate();
    document.body.classList.add("data-loaded");
  } catch (e) {
    if (e.status === 403 && String(e.message).startsWith("PASSWORD_CHANGE_REQUIRED")) {
      showPasswordChange();
      return;
    }
    if (e.status !== 401) toast("Couldn't load workspace: " + e.message);
  }
}
function render() {
  const d = data.dashboard;
  const isBarber = authUser?.role === "barber";
  $("#stats").innerHTML = [
    [isBarber ? "Your visits" : "Completed visits", d.total_visits, isBarber ? "Visits assigned to you" : "Across all branches"],
    [isBarber ? "Your service total" : "Service revenue", money(d.revenue), isBarber ? "Recorded service value" : "Demo visit history"],
    ["Average rating", d.average_rating ?? "—", "Out of 5 · " + d.feedback_count + " responses"],
    [isBarber ? "Repeat clients" : "Open recovery tasks", isBarber ? (d.repeat_customer_rate ?? 0) + "%" : d.open_recovery_tasks, isBarber ? "Customers who returned to you" : "Issues needing attention"]
  ].map(x => `<article class="stat"><span>${x[0]}</span><strong>${x[1]}</strong><small>${x[2]}</small></article>`).join("");

  $("#feedback").innerHTML = data.feedback.length ? data.feedback.map(f => `
    <div class="item feedback-card" data-feedback-visit="${f.visit_id}" role="button" tabindex="0"><div class="rating">${f.rating}/5</div><div class="item-content">
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
    </div>`).join("") || '<div class="empty">No branch data available.</div>';

  const employeeMax = Math.max(1, ...data.insights.barbers.map(b => b.revenue));
  $("#employeeInsights").innerHTML = data.insights.barbers.map(b => `
    <div class="branch"><div class="branch-top"><strong>${esc(b.barber_name)}</strong><span>${money(b.revenue)}</span></div>
      <div class="track"><div class="fill" style="width:${b.revenue/employeeMax*100}%"></div></div>
      <div class="meta">${esc(b.branch_name.replace("The Gentlemen's Club — ",""))} · ${b.visits} visits · ${b.feedback_count} feedback responses · rating ${b.average_rating ?? "—"}</div>
    </div>`).join("") || '<div class="empty">No employee performance data yet.</div>';

  $("#visits").innerHTML = data.visits.length ? `<div class="visit-list-hint">Select any row to open the complete record and saved versions.</div><div class="table-wrap"><table class="table visit-table"><thead><tr>
    <th>CUSTOMER</th><th>VISIT DATE</th><th>SERVICE</th><th>TOTAL</th><th>FEEDBACK</th><th>ACTIONS</th>
    </tr></thead><tbody>${data.visits.slice(0,100).map(v => `
      <tr class="visit-row" data-open-visit="${v.id}" tabindex="0" role="button" aria-label="Open visit record ${v.id} for ${esc(v.customer_name)}">
        <td><strong>${esc(v.customer_name)}</strong><br><span class="meta">${esc(v.customer_phone || "Phone not added")} · ${esc(v.customer_location || "Location not added")}</span><br><span class="meta">Record #${v.id}</span></td>
        <td>${dateTime(v.completed_at)}<br><span class="meta">${esc(v.branch_name.replace("The Gentlemen's Club — ",""))} · ${esc(v.barber_name)}</span></td>
        <td>${esc(v.service_name)}</td><td><strong>${money(v.amount)}</strong></td>
        <td>${v.rating ? v.rating + "/5 customer feedback" : "Awaiting"}${v.customer_rating ? `<br><span class="meta">Interaction ${v.customer_rating}/5</span>` : ""}</td>
        <td class="visit-actions"><button class="secondary" type="button" data-open-visit-button="${v.id}">Details</button><button class="secondary" type="button" data-edit-visit="${v.id}">Edit</button>
          ${isBarber ? `<button class="secondary" type="button" data-rate-visit="${v.id}">${v.customer_rating ? "Edit note" : "Rate interaction"}</button>` : ""}</td>
      </tr>`).join("")}</tbody></table></div>` : '<div class="empty">No visit entries yet. Start a check-in to create your first record.</div>';

  $("#barberCustomers").innerHTML = data.customers.length ? `<div class="customer-directory">${data.customers.map(customer => {
    const lastVisit = data.visits.find(visit => visit.customer_id === customer.id);
    return `<button type="button" class="customer-card" data-open-customer="${customer.id}">
      <span class="customer-avatar">${esc((customer.name || "?").slice(0,1).toUpperCase())}</span>
      <span class="customer-card-main"><strong>${esc(customer.name)}</strong><small>${esc(customer.phone || "No phone saved")}</small><small>${esc(customer.location || "Location not added")}</small></span>
      <span class="customer-card-meta"><strong>${customer.visit_count} visits</strong><small>${lastVisit ? "Last visit " + date(lastVisit.completed_at) : "No recent visit loaded"}</small></span>
      <span class="customer-chevron">›</span>
    </button>`;
  }).join("")}</div>` : '<div class="empty">Your customer list will appear after you record visits.</div>';

  $("#activityLog").innerHTML = (data.auditLogs || []).map(entry => `
    <div class="audit-entry"><div class="audit-dot"></div><div class="audit-body">
      <strong>${esc(entry.actor_username)} <span class="meta">${esc(entry.actor_role)}</span></strong>
      <p>${esc(entry.action.replaceAll(".", " · ").replaceAll("_", " "))} · ${esc(entry.entity_type)} #${entry.entity_id}</p>
      ${entry.change_note ? `<p class="meta">${esc(entry.change_note)}</p>` : ""}
      <span class="meta">${dateTime(entry.created_at)}</span>
    </div></div>`).join("") || '<div class="empty">Saved changes will appear here.</div>';

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
  editingVisitId = null;
  $("#visitForm").reset();
  $("#editReasonLabel").hidden = true;
  $("#changeNote").value = "";
  $("#customerTypeOptions").hidden = false;
  $("#visitDialog").querySelector(".eyebrow").textContent = "CLIENT CHECK-IN";
  $("#visitDialog").querySelector("h2").textContent = "Start a better visit";
  $("#saveVisit").textContent = "Complete check-in";
  $("input[name='customer_type'][value='new']").checked = true;
  selectedCustomerCandidate = null;
  confirmedCustomer = null;
  $("#customerSearch").value = "";
  $("#customerSearchResults").innerHTML = '<p class="empty">Enter at least 3 characters to search existing customers.</p>';
  $("#customerSearchLabel").hidden = false;
  $("#customerSearchResults").hidden = false;
  $("#selectedCustomerConfirm").hidden = true;
  $("#newCustomerMatchNotice").hidden = true;
  $("#visitDateTime").value = localDateTimeValue(new Date());
  lastCustomerSearchMatches = [];
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
  $("#newCustomerPhone").required = isNew && !editingVisitId;
  $("#newCustomerName").required = isNew && !editingVisitId;
  // Edit mode already has a confirmed customer and hides the search control.
  // A hidden required search input blocks the browser's submit event before fetch runs.
  $("#customerSearch").required = !isNew && !editingVisitId;
  if (isNew) {
    selectedCustomerCandidate = null;
    confirmedCustomer = null;
    $("#selectedCustomerConfirm").hidden = true;
  } else {
    $("#newCustomerMatchNotice").hidden = true;
    $("#customerSearchLabel").hidden = false;
    $("#customerSearchResults").hidden = false;
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
  lastCustomerSearchMatches = matches;
  if (!matches.length) {
    box.innerHTML = `<p class="empty">No customer found for “${esc(term)}”. If they're new, switch to New customer.</p>`;
    return;
  }
  box.innerHTML = matches.map(c => `
    <article class="customer-result"><div><strong>${esc(c.name)}</strong><div class="meta">${esc(c.phone || "No phone saved")} · ${esc(c.location || "Location not added")}</div>
      <div class="meta">${c.visit_count} previous visit${c.visit_count===1?"":"s"}${c.last_visit ? " · Last visit " + dateTime(c.last_visit) : ""}</div></div>
      <button type="button" class="secondary" data-review-customer="${c.id}">Review</button></article>`).join("");
}
async function searchReturningCustomer() {
  const term = $("#customerSearch").value.trim();
  const requestId = ++customerSearchSequence;
  selectedCustomerCandidate = null;
  confirmedCustomer = null;
  $("#customerSearchLabel").hidden = false;
  $("#customerSearchResults").hidden = false;
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
function renderConfirmedClientCard(candidate, {editable = true, showPrevious = true} = {}) {
  const card = $("#selectedCustomerConfirm");
  card.innerHTML = `<div class="confirmed-banner">✓ ${editable ? "CLIENT SELECTED" : "CLIENT CONFIRMED"}</div>
    <strong>${esc(candidate.name)}</strong>
    <div class="client-profile-details"><span><b>Phone</b> ${esc(candidate.phone || "No phone saved")}</span><span><b>Area</b> ${esc(candidate.location || "Not added")}</span></div>
    ${showPrevious ? `<div class="meta">${candidate.visit_count || 0} previous visit${candidate.visit_count===1?"":"s"}${candidate.last_visit ? " · Last visit " + dateTime(candidate.last_visit) : ""}</div>` : ""}
    ${editable ? '<button type="button" class="text-action" data-change-customer>Change / search another client</button>' : ""}`;
  card.hidden = false;
}
function openEditVisit(id) {
  const visit = data.visits.find(item => item.id === id);
  if (!visit) return toast("Visit not found in this workspace. Refresh and try again.");
  openVisitDialog();
  editingVisitId = visit.id;
  $("#visitDialog").querySelector(".eyebrow").textContent = "VERSIONED EDIT";
  $("#visitDialog").querySelector("h2").textContent = "Update visit record";
  $("#saveVisit").textContent = "Save changes";
  $("#editReasonLabel").hidden = false;
  $("#customerTypeOptions").hidden = true;
  $("input[name='customer_type'][value='returning']").checked = true;
  toggleCustomerType();
  const customer = data.customers.find(item => item.id === visit.customer_id) || {
    id: visit.customer_id, name: visit.customer_name, phone: visit.customer_phone,
    location: visit.customer_location, visit_count: 0, last_visit: visit.completed_at
  };
  confirmedCustomer = customer;
  selectedCustomerCandidate = customer;
  $("#customerSearchLabel").hidden = true;
  $("#customerSearchResults").hidden = true;
  renderConfirmedClientCard(customer);
  $("#branch").value = String(visit.branch_id);
  populateBarbers();
  $("#barber").value = String(visit.barber_id);
  $("#visitDateTime").value = localDateTimeValue(new Date(visit.completed_at));
  $("input[name='messaging_consent']").checked = Boolean(visit.feedback_requested);
  $("#serviceRows").innerHTML = "";
  const lines = visit.service_items?.length ? visit.service_items : [{
    service_name: visit.service_name, quantity: 1, unit_price: visit.amount
  }];
  lines.forEach(line => addServiceRow(line));
  calcTotal();
}
async function openVisitHistory(id) {
  $("#historyContent").innerHTML = '<p class="empty">Loading history…</p>';
  $("#historyDialog").showModal();
  try {
    const entries = await api("/api/visits/" + id + "/history");
    $("#historyContent").innerHTML = entries.length ? entries.map(entry => `
      <article class="version-card">
        <div class="version-heading"><strong>Version ${entry.id} · ${esc(entry.action.replaceAll(".", " · ").replaceAll("_", " "))}</strong><span class="meta">${dateTime(entry.created_at)}</span></div>
        <p class="meta">Changed by ${esc(entry.actor_username)} · ${esc(entry.actor_role)} ${entry.change_note ? " · " + esc(entry.change_note) : ""}</p>
        ${entry.before_data ? `<details><summary>Before this change</summary><pre>${esc(JSON.stringify(entry.before_data, null, 2))}</pre></details>` : '<p class="meta">No previous version — this is the original entry.</p>'}
        ${entry.after_data ? `<details><summary>Saved version</summary><pre>${esc(JSON.stringify(entry.after_data, null, 2))}</pre></details>` : ""}
      </article>`).join("") : '<div class="empty">No edits have been made. The original version is the current record.</div>';
  } catch (err) {
    $("#historyContent").innerHTML = `<p class="form-error">${esc(err.message)}</p>`;
  }
}
let selectedVisitDetailId = null;
function showSnapshot(snapshot, includeVisitDetails = true) {
  if (!snapshot) return '<p class="meta">No snapshot available for this version.</p>';
  const lines = Array.isArray(snapshot.service_items) && snapshot.service_items.length
    ? snapshot.service_items.map(line => `<div class="detail-line"><span>${esc(line.service_name)} × ${line.quantity}</span><span>${money(line.line_total)}</span></div>`).join("")
    : `<div class="detail-line"><span>${esc(snapshot.service_name || "Service not specified")}</span><span>${money(snapshot.amount)}</span></div>`;
  return `<div class="snapshot-summary">
    ${includeVisitDetails ? `<div class="detail-pair"><span>Customer</span><strong>${esc(snapshot.customer_name || "—")}</strong></div>
    <div class="detail-pair"><span>Branch / barber</span><strong>${esc((snapshot.branch_name || "—").replace("The Gentlemen's Club — ",""))} · ${esc(snapshot.barber_name || "—")}</strong></div>
    <div class="detail-pair"><span>Visit date</span><strong>${dateTime(snapshot.completed_at)}</strong></div>` : ""}
    <div class="detail-service-list">${lines}</div>
    <div class="detail-total"><span>Total</span><strong>${money(snapshot.amount)}</strong></div>
  </div>`;
}
async function openVisitDetails(id) {
  const visit = data.visits.find(item => item.id === id);
  if (!visit) return toast("This visit isn't in the loaded list. Refresh and try again.");
  selectedVisitDetailId = id;
  $("#visitDetailsTitle").textContent = "Visit #" + id;
  $("#visitDetailsContent").innerHTML = '<p class="empty">Loading complete visit record…</p>';
  $("#visitDetailsVersions").innerHTML = '<p class="empty">Loading saved versions…</p>';
  $("#visitDetailsDialog").showModal();
  const feedback = data.feedback.find(item => item.visit_id === id);
  $("#visitDetailsContent").innerHTML = `
    <div class="visit-detail-grid">
      <section class="detail-card">
        <p class="detail-overline">CUSTOMER</p><h3>${esc(visit.customer_name)}</h3>
        <div class="detail-pair"><span>Phone</span><strong>${esc(visit.customer_phone || "Not provided")}</strong></div>
        <div class="detail-pair"><span>Area</span><strong>${esc(visit.customer_location || "Not provided")}</strong></div>
      </section>
      <section class="detail-card">
        <p class="detail-overline">VISIT</p><h3>${esc(visit.branch_name.replace("The Gentlemen's Club — ",""))}</h3>
        <div class="detail-pair"><span>Barber</span><strong>${esc(visit.barber_name)}</strong></div>
        <div class="detail-pair"><span>Completed</span><strong>${dateTime(visit.completed_at)}</strong></div>
        <div class="detail-pair"><span>Record ID</span><strong>#${visit.id}</strong></div>
      </section>
    </div>
    <section class="detail-card detail-services"><p class="detail-overline">SERVICES &amp; TOTAL</p>
      ${showSnapshot(visit, false)}
    </section>
    <div class="visit-detail-grid">
      <section class="detail-card"><p class="detail-overline">CUSTOMER FEEDBACK</p>
        <h3>${visit.rating ? visit.rating + " / 5" : "Awaiting feedback"}</h3>
        <p>${esc(feedback?.comment || "No written feedback recorded for this visit.")}</p>
      </section>
      ${authUser?.role === "barber" ? `<section class="detail-card"><p class="detail-overline">INTERACTION NOTE</p>
        <h3>${visit.customer_rating ? visit.customer_rating + " / 5" : "Not rated"}</h3>
        <p>${esc(visit.customer_rating_note || "No visit-specific interaction note yet.")}</p>
        <button type="button" class="secondary" data-detail-rate="${visit.id}">${visit.customer_rating ? "Edit interaction note" : "Add interaction note"}</button>
      </section>` : ""}
    </div>`;
  try {
    const entries = await api("/api/visits/" + id + "/history");
    $("#visitDetailsVersions").innerHTML = entries.length ? entries.map((entry, index) => `
      <article class="version-card">
        <div class="version-heading"><strong>Version ${entries.length - index} · ${esc(entry.action === "visit.create" ? "Record created" : "Record updated")}</strong><time class="meta">${dateTime(entry.created_at)}</time></div>
        <p class="version-actor">By <strong>${esc(entry.actor_username)}</strong> · ${esc(entry.actor_role)}</p>
        ${entry.change_note ? `<p class="version-note">${esc(entry.change_note)}</p>` : ""}
        <div class="version-snapshots">
          ${entry.before_data ? `<details><summary>Before this update</summary>${showSnapshot(entry.before_data)}<details class="raw-snapshot"><summary>Full saved fields</summary><pre>${esc(JSON.stringify(entry.before_data, null, 2))}</pre></details></details>` : '<p class="version-original">Original entry — no previous version.</p>'}
          ${entry.after_data ? `<details><summary>Version contents</summary>${showSnapshot(entry.after_data)}<details class="raw-snapshot"><summary>Full saved fields</summary><pre>${esc(JSON.stringify(entry.after_data, null, 2))}</pre></details></details>` : ""}
        </div>
      </article>`).join("") : '<div class="empty">No audit versions were found for this record yet.</div>';
  } catch (err) {
    $("#visitDetailsVersions").innerHTML = `<p class="form-error">Couldn't load version history: ${esc(err.message)}</p>`;
  }
}
function openCustomerRating(id) {
  const visit = data.visits.find(item => item.id === id);
  if (!visit) return toast("Visit not found. Refresh and try again.");
  $("#customerRatingForm").reset();
  $("#customerRatingVisitId").value = String(visit.id);
  $("#customerRatingClient").innerHTML = `<strong>${esc(visit.customer_name)}</strong><span class="meta">Visit #${visit.id} · ${esc(visit.branch_name)}</span>`;
  $("#customerRatingForm").elements.rating.value = String(visit.customer_rating || 5);
  $("#customerRatingForm").elements.note.value = visit.customer_rating_note || "";
  $("#customerRatingDialog").showModal();
}
function reviewCustomer(id) {
  const candidate = lastCustomerSearchMatches.find(c => c.id === id) ||
    data.customers.find(c => c.id === id) || selectedCustomerCandidate;
  if (!candidate || candidate.id !== id) {
    toast("Please search for the customer again.");
    return;
  }
  selectedCustomerCandidate = candidate;
  confirmedCustomer = null;
  $("#customerSearchLabel").hidden = true;
  $("#customerSearchResults").hidden = true;
  const card = $("#selectedCustomerConfirm");
  card.innerHTML = `<div class="selected-customer-title">Is this the right client?</div>
    <strong>${esc(candidate.name)}</strong>
    <div class="client-profile-details"><span><b>Phone</b> ${esc(candidate.phone || "Not saved")}</span><span><b>Area</b> ${esc(candidate.location || "Not added")}</span></div>
    <div class="meta">${candidate.visit_count} previous visit${candidate.visit_count===1?"":"s"}${candidate.last_visit ? " · Last visit " + dateTime(candidate.last_visit) : ""}</div>
    <div class="confirm-actions"><button type="button" class="primary" data-confirm-customer="${candidate.id}">Confirm client</button><button type="button" class="secondary" data-change-customer>Search another</button></div>`;
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
$("#newVisitOwner").onclick = openVisitDialog;
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
    lastCustomerSearchMatches = matches;
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
    $("#customerSearchLabel").hidden = true;
    $("#customerSearchResults").hidden = true;
    $("#selectedCustomerConfirm").innerHTML = `<div class="confirmed-banner">✓ CLIENT CONFIRMED</div><strong>${esc(c.name)}</strong>
      <div class="client-profile-details"><span><b>Phone</b> ${esc(c.phone || "No phone saved")}</span><span><b>Area</b> ${esc(c.location || "Not added")}</span></div>
      <div class="meta">${c.visit_count} previous visit${c.visit_count===1?"":"s"}${c.last_visit ? " · Last visit " + dateTime(c.last_visit) : ""}</div>
      <button type="button" class="text-action" data-change-customer>Change / search another client</button>`;
    toast("Client confirmed. Add visit details below.");
  }
  if (e.target.closest("[data-change-customer]")) {
    confirmedCustomer = null;
    selectedCustomerCandidate = null;
    lastCustomerSearchMatches = [];
    $("#selectedCustomerConfirm").hidden = true;
    $("#customerSearchLabel").hidden = false;
    $("#customerSearchResults").hidden = false;
    $("#customerSearch").value = "";
    $("#customerSearchResults").innerHTML = '<p class="empty">Enter at least 3 characters to search existing customers.</p>';
    $("#customerSearch").focus();
  }
});
$("#newCustomerMatchNotice").addEventListener("click", e => {
  const b = e.target.closest("[data-use-existing]");
  if (b) useExistingCustomer(Number(b.dataset.useExisting));
});
$("#newCustomerPhone").addEventListener("blur", checkNewCustomerPhone);

$("#visits").addEventListener("click", async e => {
  const edit = e.target.closest("[data-edit-visit]");
  const history = e.target.closest("[data-history-visit]");
  const rate = e.target.closest("[data-rate-visit]");
  const detailsButton = e.target.closest("[data-open-visit-button]");
  const row = e.target.closest("[data-open-visit]");
  if (edit) return openEditVisit(Number(edit.dataset.editVisit));
  if (history) return openVisitHistory(Number(history.dataset.historyVisit));
  if (rate) return openCustomerRating(Number(rate.dataset.rateVisit));
  if (detailsButton) return openVisitDetails(Number(detailsButton.dataset.openVisitButton));
  if (row) return openVisitDetails(Number(row.dataset.openVisit));
});
$("#visits").addEventListener("keydown", e => {
  const row = e.target.closest("[data-open-visit]");
  if (!row || e.target.closest("button") || !["Enter", " "].includes(e.key)) return;
  e.preventDefault();
  openVisitDetails(Number(row.dataset.openVisit));
});
$("#visitDetailsContent").addEventListener("click", e => {
  const rate = e.target.closest("[data-detail-rate]");
  if (rate) {
    $("#visitDetailsDialog").close();
    openCustomerRating(Number(rate.dataset.detailRate));
  }
});
$("#editVisitFromDetails").addEventListener("click", () => {
  if (!selectedVisitDetailId) return;
  const id = selectedVisitDetailId;
  $("#visitDetailsDialog").close();
  openEditVisit(id);
});
$("#barberCustomers").addEventListener("click", e => {
  const card = e.target.closest("[data-open-customer]");
  if (!card) return;
  const customerId = Number(card.dataset.openCustomer);
  const recentVisit = data.visits.find(visit => visit.customer_id === customerId);
  if (!recentVisit) {
    toast("No recent visit is in the loaded list for this customer yet.");
    return;
  }
  openVisitDetails(recentVisit.id);
});
$("#feedback").addEventListener("click", e => {
  const card = e.target.closest("[data-feedback-visit]");
  if (card) openVisitDetails(Number(card.dataset.feedbackVisit));
});
$("#refreshAudit").addEventListener("click", async () => {
  try {
    data.auditLogs = await api("/api/audit-logs?limit=50");
    render();
    toast("Audit history refreshed.");
  } catch (err) { toast(err.message); }
});
$("#customerRatingForm").onsubmit = async e => {
  e.preventDefault();
  const form = new FormData(e.target);
  const button = $("#saveCustomerRating");
  button.disabled = true;
  try {
    await api("/api/customer-ratings", {method:"POST", body:JSON.stringify({
      visit_id: Number(form.get("visit_id")),
      rating: Number(form.get("rating")),
      note: String(form.get("note") || "").trim()
    })});
    $("#customerRatingDialog").close();
    await load();
    toast("Visit interaction note saved to the audit trail.");
  } catch (err) { toast(err.message); }
  finally { button.disabled = false; }
};

$("#visitForm").onsubmit = async e => {
  e.preventDefault();
  const type = $("input[name='customer_type']:checked").value;
  const services = readServices();
  if (!services.length || services.some(s => !s.service_name || !Number.isInteger(s.quantity) || s.quantity < 1 || !Number.isFinite(s.unit_price) || s.unit_price < 0)) {
    toast("Check each service, quantity, and price.");
    return;
  }
  const visitDateTimeValue = $("#visitDateTime").value;
  if (!visitDateTimeValue) {
    toast("Please enter the visit date and time.");
    return;
  }
  const completedAt = new Date(visitDateTimeValue);
  if (Number.isNaN(completedAt.getTime())) {
    toast("Please enter a valid visit date and time.");
    return;
  }
  if (completedAt.getTime() > Date.now() + 60_000) {
    toast("A completed visit cannot be in the future. Check the date and time.");
    return;
  }
  const payload = {
    branch_id: Number($("#branch").value),
    barber_id: Number($("#barber").value),
    completed_at: completedAt.toISOString(),
    services,
    messaging_consent: $("input[name='messaging_consent']").checked
  };
  if (editingVisitId) {
    if (!confirmedCustomer) {
      toast("Select and confirm the customer for this visit before saving.");
      return;
    }
    payload.customer_id = confirmedCustomer.id;
    payload.change_note = $("#changeNote").value.trim();
  } else if (type === "returning") {
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
  const wasEditing = Boolean(editingVisitId);
  save.disabled = true;
  save.textContent = "Saving…";
  try {
    const result = wasEditing
      ? await api("/api/visits/" + editingVisitId, {method:"PATCH", body:JSON.stringify(payload)})
      : await api("/api/visits", {method:"POST", body:JSON.stringify(payload)});
    $("#visitDialog").close();
    editingVisitId = null;
    await load();
    toast(wasEditing
      ? "Visit updated. The previous version is preserved in history."
      : `Check-in saved · Total ${money(result.visit.amount)}. ${result.notice}`);
  } catch (err) {
    toast(err.message);
  } finally {
    save.disabled = false;
    save.textContent = editingVisitId ? "Save changes" : "Complete check-in";
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
initAuth();
