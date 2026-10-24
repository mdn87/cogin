"use strict";
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem("cogin-review-token") || "";
sessionStorage.setItem("cogin-review-token", token);
history.replaceState(null, "", location.pathname);
let data, draft, current = 0, timer, saving = Promise.resolve(), saveFailed = false, submitting = false;
let editVersion = 0, savedVersion = 0;
let sessions = {sessions: [], pending: null, running: false}, actionBusy = false;
const showError = error => { $("error").textContent = error.message || String(error); $("error").hidden = false; };
async function api(path, body) {
  const response = await fetch("/api/" + path, {method: body === undefined ? "GET" : "POST", headers: {"X-Review-Token": token, "Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}
function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; }
const complete = entry => entry.reviewed && entry.reason.trim();
function updateProgress() {
  const finished = Object.values(draft.cases).filter(complete).length;
  $("progress").textContent = `${finished} of ${data.cases.length} reviewed`;
  $("count").textContent = `${draft.cases[data.cases[current].id].selected.length} cleanup lines selected`;
  $("submit").disabled = data.locked || submitting || saveFailed || finished !== data.cases.length || !draft.reviewer.trim() || !draft.blind_attestation;
  $("cases").replaceChildren(...data.cases.map((item, index) => {
    const button = node("button", undefined, "case-button");
    button.append(node("span", `Patch ${index + 1}`), node("small", complete(draft.cases[item.id]) ? "Reviewed ✓" : "To review"));
    button.setAttribute("aria-pressed", String(index === current));
    button.onclick = () => { current = index; renderCase(); };
    return button;
  }));
}
function queueSave() {
  clearTimeout(timer); timer = null;
  if (data.locked || saveFailed) return saving;
  const snapshot = structuredClone(draft);
  const version = editVersion;
  saving = saving.then(async () => {
    if (saveFailed) return;
    snapshot.revision = draft.revision;
    try { const result = await api("draft", snapshot); draft.revision = result.revision; savedVersion = version; $("save-state").textContent = savedVersion === editVersion ? "Saved on this computer" : "Saving…"; }
    catch (error) { saveFailed = true; $("save-state").textContent = "Save failed — reload before continuing"; showError(error); updateProgress(); }
  });
  return saving;
}
function changed() {
  $("submit-confirmation").hidden = true;
  editVersion++;
  $("save-state").textContent = "Saving…";
  clearTimeout(timer); timer = setTimeout(queueSave, 250); updateProgress();
}
function renderCase() {
  const item = data.cases[current], entry = draft.cases[item.id];
  $("case-id").textContent = item.id;
  $("patch-title").textContent = `Patch ${current + 1} · ${item.changed_lines} changed lines`;
  $("diff").replaceChildren(...item.lines.map(line => {
    const row = node("div", undefined, `diff-line ${line.kind}${entry.selected.includes(line.change_id) ? " selected" : ""}`);
    const slot = node("span", undefined, "line-selector");
    if (line.change_id !== null) {
      const check = document.createElement("input"); check.type = "checkbox"; check.checked = entry.selected.includes(line.change_id); check.disabled = data.locked || submitting;
      check.setAttribute("aria-label", `Revert changed line ${line.change_id + 1}: ${line.text}`);
      check.onchange = () => { entry.selected = check.checked ? [...entry.selected, line.change_id] : entry.selected.filter(n => n !== line.change_id); entry.reviewed = false; $("reviewed").checked = false; row.classList.toggle("selected", check.checked); changed(); };
      slot.append(check);
    }
    row.append(slot, node("span", line.old ?? "", "line-number"), node("span", line.new ?? "", "line-number"), node("span", line.text, "line-text"));
    return row;
  }));
  $("reason").value = entry.reason; $("reviewed").checked = entry.reviewed;
  $("scoring").disabled = data.locked || submitting;
  $("previous").disabled = current === 0; $("next").disabled = current === data.cases.length - 1;
  $("reviewer").disabled = $("attestation").disabled = data.locked || submitting;
  $("submitted").hidden = !data.locked;
  $("confirm-submit").disabled = $("cancel-submit").disabled = submitting;
  if (data.locked) $("submit-confirmation").hidden = true;
  if (data.locked) $("save-state").textContent = "Submitted · scores locked";
  updateProgress();
}
$("reason").oninput = () => { draft.cases[data.cases[current].id].reason = $("reason").value; changed(); };
$("reviewed").onchange = () => { draft.cases[data.cases[current].id].reviewed = $("reviewed").checked; changed(); };
$("zero").onclick = () => { Object.assign(draft.cases[data.cases[current].id], {selected: [], reviewed: true}); changed(); renderCase(); $("reason").focus(); };
$("reviewer").oninput = () => { draft.reviewer = $("reviewer").value; changed(); };
$("attestation").onchange = () => { draft.blind_attestation = $("attestation").checked; changed(); };
$("previous").onclick = () => { current--; renderCase(); };
$("next").onclick = () => { current++; renderCase(); };
$("submit").onclick = () => {
  $("submit-status").textContent = "";
  $("submit-confirmation").hidden = false;
  $("confirm-submit").focus();
};
$("cancel-submit").onclick = () => {
  $("submit-confirmation").hidden = true;
  $("submit").focus();
};
$("confirm-submit").onclick = async () => {
  if ($("submit").disabled || $("submit-confirmation").hidden) return;
  $("submit-status").textContent = "Saving and submitting your review…";
  submitting = true; renderCase();
  try { await queueSave(); if (saveFailed) throw new Error("Your latest changes could not be saved. Reload before submitting."); await api("submit", {revision: draft.revision}); data.locked = true; }
  catch (error) { $("submit-status").textContent = error.message; showError(error); }
  finally { submitting = false; renderCase(); }
};
for (const name of ["review", "sessions"]) $(name + "-tab").onclick = () => {
  for (const other of ["review", "sessions"]) { $(other + "-panel").hidden = other !== name; $(other + "-tab").setAttribute("aria-pressed", String(other === name)); }
};
function renderSessions() {
  $("start-claude").disabled = $("start-codex").disabled = sessions.running || actionBusy || !$("operator").value.trim();
  $("operator").disabled = sessions.running || actionBusy;
  $("stop").hidden = !sessions.running; $("stop").disabled = actionBusy;
  $("session-status").textContent = sessions.running ? "Session running. Waiting for the CLI or checking its result…" : "No session running.";
  $("approval").hidden = !sessions.pending; $("no-request").hidden = !!sessions.pending;
  $("no-request").textContent = sessions.running
    ? "No approval request is pending. The CLI may work without prompting; requests appear here only when it asks for a decision."
    : sessions.sessions.length
      ? "No approval request is pending. The last session ended; see its result below."
      : "No session is running. Start a session to collect approvals.";
  $("payload").textContent = sessions.pending ? JSON.stringify(sessions.pending.payload, null, 2) : "";
  $("allow").disabled = $("deny").disabled = actionBusy;
  $("history").replaceChildren(...sessions.sessions.map(item => {
    const row = node("div", undefined, "session-row");
    row.append(node("strong", `${item.lane === "claude" ? "Claude" : "Codex"} · ${item.status}`), node("p", `Interruptions: ${item.interruptions ?? "unmeasured"} · Task: ${item.task_passed == null ? "unmeasured" : item.task_passed ? "passed" : "did not pass"}`));
    if (item.error) row.append(node("p", item.error));
    return row;
  }));
  if (!sessions.sessions.length) $("history").textContent = "No sessions collected yet.";
}
async function refreshSessions() { sessions = await api("sessions"); renderSessions(); }
async function sessionAction(path, body) {
  actionBusy = true; renderSessions();
  try { await api(path, body); await refreshSessions(); }
  catch (error) { showError(error); }
  finally { actionBusy = false; renderSessions(); }
}
$("operator").oninput = renderSessions;
for (const lane of ["claude", "codex"]) $("start-" + lane).onclick = () => sessionAction("start", {lane, operator: $("operator").value});
for (const decision of ["allow", "deny"]) $(decision).onclick = () => {
  if (sessions.pending) sessionAction("decision", {session_id: sessions.sessions.at(-1).id, request_id: sessions.pending.request_id, decision});
};
$("stop").onclick = () => sessionAction("stop", {session_id: sessions.sessions.at(-1).id});
window.addEventListener("beforeunload", event => { if (savedVersion !== editVersion) { event.preventDefault(); event.returnValue = ""; } });
(async () => {
  try {
    data = await api("review"); draft = structuredClone(data.draft);
    $("task").textContent = data.task;
    $("base").replaceChildren(...Object.entries(data.base).map(([name, text]) => { const details = node("details"); details.append(node("summary", name), node("pre", text)); return details; }));
    $("reviewer").value = draft.reviewer; $("attestation").checked = draft.blind_attestation;
    $("save-state").textContent = "Saved on this computer"; renderCase();
    await refreshSessions();
    const poll = async () => { try { await refreshSessions(); } catch (error) { showError(error); } finally { setTimeout(poll, 1000); } }; setTimeout(poll, 1000);
  } catch (error) { showError(error); }
})();
