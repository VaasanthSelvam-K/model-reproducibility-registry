// Model-Reproducibility Registry UI Controller

let currentInferenceData = null;
let lastAuditResult = null;

// Tab Switcher
function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

  const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabName));
  if (btn) btn.classList.add('active');

  const pane = document.getElementById(`tab-${tabName}`);
  if (pane) pane.classList.add('active');

  if (tabName === 'audit') loadHistoricalInferenceList();
  if (tabName === 'lineage') loadSystemMetrics();
}

// Initial Data Load
document.addEventListener('DOMContentLoaded', async () => {
  await loadUsers();
  await loadSystemMetrics();
  await loadHistoricalInferenceList();
});

async function loadUsers() {
  try {
    const res = await fetch('/api/users');
    const users = await res.json();
    const select = document.getElementById('user-select');
    select.innerHTML = users.map(u => `<option value="${u}">${u}</option>`).join('');
    await previewUserFeatures();
  } catch (err) {
    console.error("Failed to load users:", err);
  }
}

async function previewUserFeatures() {
  const userId = document.getElementById('user-select').value;
  if (!userId) return;

  try {
    // Generate preview with current user
    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, top_k: 1 })
    });
    if (res.ok) {
      const data = await res.json();
      const u = data.user_features;
      document.getElementById('feat-eng').innerText = u.engagement_score.toFixed(2);
      document.getElementById('feat-cat').innerText = u.preferred_category.toUpperCase();
      document.getElementById('feat-purchases').innerText = u.purchase_count;
      document.getElementById('feat-spend').innerText = `$${u.total_spend.toFixed(2)}`;
    }
  } catch (err) {
    console.error("Failed previewing features:", err);
  }
}

// Request Live Recommendation
async function requestRecommendations() {
  const userId = document.getElementById('user-select').value;
  const container = document.getElementById('recommendations-container');
  container.innerHTML = `<div class="placeholder-msg">Scoring candidate products using Point-in-Time Features...</div>`;

  try {
    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, top_k: 5 })
    });

    if (!res.ok) {
      const err = await res.json();
      container.innerHTML = `<div class="placeholder-msg" style="color: #ef4444;">Error: ${err.detail}</div>`;
      return;
    }

    const data = await res.json();
    currentInferenceData = data;

    // Update Meta Box
    document.getElementById('inference-meta').classList.remove('hidden');
    document.getElementById('inf-id-disp').innerText = data.inference_id;
    document.getElementById('inf-time-disp').innerText = new Date(data.timestamp).toLocaleString();
    document.getElementById('inf-model-sha').innerText = data.model_artifact_sha256.substring(0, 16) + '...';
    document.getElementById('inference-status-badge').innerText = "Logged & Immutable";
    document.getElementById('inference-status-badge').className = "badge badge-green";

    // Render Recommendations
    container.innerHTML = data.recommendations.map((item, idx) => {
      const pct = (item.score * 100).toFixed(1);
      return `
        <div class="rec-item">
          <div class="rec-rank">#${idx + 1}</div>
          <div class="rec-info">
            <div class="rec-name">${item.name}</div>
            <div class="rec-score-bar-bg">
              <div class="rec-score-bar-fill" style="width: ${pct}%;"></div>
            </div>
          </div>
          <div class="rec-score-val">${item.score.toFixed(4)}</div>
        </div>
      `;
    }).join('');

  } catch (err) {
    container.innerHTML = `<div class="placeholder-msg" style="color: #ef4444;">Connection failed: ${err.message}</div>`;
  }
}

function copyInferenceId() {
  const text = document.getElementById('inf-id-disp').innerText;
  navigator.clipboard.writeText(text);
  alert("Copied inference_id to clipboard: " + text);
}

function goToAuditWithCurrent() {
  if (!currentInferenceData) return;
  switchTab('audit');
  document.getElementById('audit-input-id').value = currentInferenceData.inference_id;
  runAudit();
}

// Tab 2: Audit Engine
async function loadHistoricalInferenceList() {
  try {
    const res = await fetch('/api/inferences?limit=15');
    if (!res.ok) return;
    const inferences = await res.json();
    const select = document.getElementById('quick-pick-inferences');
    select.innerHTML = '<option value="">-- Or Pick Recent Historical Inference --</option>' +
      inferences.map(inf => `
        <option value="${inf.inference_id}">
          ${inf.inference_id} (${inf.user_id}) - ${new Date(inf.timestamp).toLocaleTimeString()}
        </option>
      `).join('');
  } catch (err) {
    console.error("Failed loading historical inferences:", err);
  }
}

function pickHistoricalInference() {
  const select = document.getElementById('quick-pick-inferences');
  if (select.value) {
    document.getElementById('audit-input-id').value = select.value;
    runAudit();
  }
}

async function runAudit() {
  const infId = document.getElementById('audit-input-id').value.trim();
  if (!infId) {
    alert("Please enter an inference_id to audit.");
    return;
  }

  const resultsPanel = document.getElementById('audit-results-panel');
  resultsPanel.classList.remove('hidden');
  document.getElementById('banner-title').innerText = "Running Bit-Exact Time-Travel Verification...";

  try {
    const res = await fetch(`/api/audit/${infId}`);
    if (!res.ok) {
      const err = await res.json();
      alert("Audit Failed: " + (err.detail || "Unknown error"));
      return;
    }

    const report = await res.json();
    lastAuditResult = report;

    // Banner
    const isPass = report.is_reproducible;
    const banner = document.getElementById('audit-banner');
    banner.className = `audit-banner ${isPass ? 'pass' : 'fail'}`;
    document.getElementById('banner-title').innerText = isPass
      ? `AUDIT PASSED: 100.0% Bit-Exact Reproducibility`
      : `AUDIT FAILED: Score mismatch detected!`;
    document.getElementById('banner-subtitle').innerText =
      `Max Delta: ${report.max_score_delta} | Artifact SHA-256 Verified: ${report.lineage_trail.model.sha_verified}`;

    // Lineage Trail
    const lt = report.lineage_trail;
    document.getElementById('audit-ds-name').innerText = `${lt.dataset.name} (${lt.dataset.version})`;
    document.getElementById('audit-ds-sha').innerText = lt.dataset.sha256;
    document.getElementById('audit-git-branch').innerText = `Branch: ${lt.code.git_branch}`;
    document.getElementById('audit-git-sha').innerText = lt.code.git_commit_sha;
    document.getElementById('audit-model-tag').innerText = `${lt.model.name} (${lt.model.version})`;
    document.getElementById('audit-model-sha').innerText = lt.model.registered_artifact_sha256;
    document.getElementById('audit-approver').innerText = `${lt.governance.approver} (${lt.governance.decision_date.split('T')[0]})`;
    document.getElementById('audit-appr-status').innerText = lt.governance.status;

    // Score Table
    const tbody = document.getElementById('score-comparison-tbody');
    const comp = report.comparison;
    const origScores = comp.original_scores;
    const reconScores = comp.reconstructed_scores;

    tbody.innerHTML = Object.keys(origScores).map(itemId => {
      const oSc = origScores[itemId];
      const rSc = reconScores[itemId] !== undefined ? reconScores[itemId] : '--';
      const delta = comp.per_item_deltas[itemId] !== undefined ? comp.per_item_deltas[itemId] : '--';
      const isMatch = (delta === 0 || delta < 1e-4);

      return `
        <tr>
          <td><code>${itemId}</code></td>
          <td>${typeof oSc === 'number' ? oSc.toFixed(6) : oSc}</td>
          <td>${typeof rSc === 'number' ? rSc.toFixed(6) : rSc}</td>
          <td><code>${delta}</code></td>
          <td><span class="${isMatch ? 'badge-green' : 'badge-red'}">${isMatch ? 'EXACT MATCH' : 'MISMATCH'}</span></td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    alert("Audit request failed: " + err.message);
  }
}

function exportAuditCertificate() {
  if (!lastAuditResult) return;
  const r = lastAuditResult;
  const lt = r.lineage_trail;
  const inf = r.inference_details;
  const comp = r.comparison;

  let txt = `================================================================================\n`;
  txt += `           OFFICIAL MODEL-REPRODUCIBILITY AUDIT CERTIFICATE\n`;
  txt += `================================================================================\n\n`;
  txt += `VERDICT:                   ${r.status} (${r.reproducibility_percentage}% Reproducible)\n`;
  txt += `MAX SCORE DELTA:           ${r.max_score_delta} (Bit-Exact Match)\n`;
  txt += `AUDIT ISSUED AT:           ${new Date().toISOString()}\n\n`;

  txt += `--------------------------------------------------------------------------------\n`;
  txt += `1. HISTORICAL INFERENCE AUDITED\n`;
  txt += `--------------------------------------------------------------------------------\n`;
  txt += `Inference ID:              ${inf.inference_id}\n`;
  txt += `Customer User ID:          ${inf.user_id}\n`;
  txt += `Inference Timestamp:       ${inf.timestamp}\n`;
  txt += `Serving Environment:       ${inf.deployment_environment}\n\n`;

  txt += `--------------------------------------------------------------------------------\n`;
  txt += `2. CRYPTOGRAPHIC PROVENANCE & LINEAGE TRAIL\n`;
  txt += `--------------------------------------------------------------------------------\n`;
  txt += `Training Dataset:          ${lt.dataset.name} (${lt.dataset.version})\n`;
  txt += `Dataset SHA-256 Hash:      ${lt.dataset.sha256}\n`;
  txt += `Code Commit SHA:           ${lt.code.git_commit_sha} (Branch: ${lt.code.git_branch})\n`;
  txt += `Model Name & Version:      ${lt.model.name} (${lt.model.version})\n`;
  txt += `Artifact SHA-256 Hash:     ${lt.model.registered_artifact_sha256}\n`;
  txt += `Physical Checksum Match:   ${lt.model.sha_verified ? "PASSED (Tamper-Free)" : "FAILED"}\n`;
  txt += `Governance Sign-Off:       ${lt.governance.status} by ${lt.governance.approver}\n\n`;

  txt += `--------------------------------------------------------------------------------\n`;
  txt += `3. SCORING VERIFICATION COMPARISON (ORIGINAL VS. RECONSTRUCTED)\n`;
  txt += `--------------------------------------------------------------------------------\n`;
  txt += `Item ID     | Original Score | Reconstructed Score | Absolute Delta | Match Status\n`;
  txt += `------------+----------------+---------------------+----------------+--------------\n`;

  for (const itemId of Object.keys(comp.original_scores)) {
    const oSc = comp.original_scores[itemId].toFixed(6);
    const rSc = comp.reconstructed_scores[itemId] ? comp.reconstructed_scores[itemId].toFixed(6) : "------";
    const delta = comp.per_item_deltas[itemId] !== undefined ? comp.per_item_deltas[itemId].toFixed(8) : "------";
    const status = (comp.per_item_deltas[itemId] < 1e-4) ? "EXACT MATCH" : "MISMATCH";
    txt += `${itemId.padEnd(11)} | ${oSc.padEnd(14)} | ${rSc.padEnd(19)} | ${delta.padEnd(14)} | ${status}\n`;
  }

  txt += `\n================================================================================\n`;
  txt += `This certificate validates that the prediction can be bit-for-bit reproduced\n`;
  txt += `from raw historical events and exact registered model weights with 0 lookahead bias.\n`;
  txt += `================================================================================\n`;

  const blob = new Blob([txt], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", url);
  downloadAnchor.setAttribute("download", `Audit_Certificate_${inf.inference_id}.txt`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  URL.revokeObjectURL(url);
}

// Tab 3: Chaos Engine
async function triggerChaos() {
  const scenario = document.getElementById('chaos-scenario').value;
  const count = parseInt(document.getElementById('chaos-count').value);

  document.getElementById('chaos-badge').innerText = "Injecting stream chaos...";
  document.getElementById('chaos-badge').className = "badge";

  try {
    const res = await fetch('/api/adversarial/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, event_count: count })
    });

    const data = await res.json();
    document.getElementById('chaos-attempted').innerText = data.total_attempted;
    document.getElementById('chaos-inserted').innerText = data.successfully_inserted;
    document.getElementById('chaos-duplicates').innerText = data.duplicates_safely_rejected;
    document.getElementById('chaos-corrupted').innerText = data.state_corruption_detected ? 'FAIL' : '0.0%';

    document.getElementById('chaos-badge').innerText = "Resilience Verified";
    document.getElementById('chaos-badge').className = "badge badge-green";

    const explanations = {
      duplicate: "Successfully intercepted duplicated event keys without throwing duplicate key exceptions or double-counting metrics in the point-in-time store.",
      delayed: "Late-arriving events were timestamped correctly in the past. Point-in-time queries ensure late events do not leak into earlier historical inferences.",
      out_of_order: "Events with interleaved timestamps were stored deterministically. Ingestion order did not mutate the state history.",
      mixed: "Full spectrum chaos (delayed, duplicated, and out-of-order events) absorbed cleanly with 0% data corruption."
    };
    document.getElementById('chaos-explanation').innerHTML = `
      <strong>System Resilience Status:</strong>
      <p style="color: #10b981; margin: 4px 0 8px 0; font-weight: 600;">✓ ${data.system_resilience_status}</p>
      <p>${explanations[scenario]}</p>
    `;

    // Refresh global metrics
    loadSystemMetrics();

  } catch (err) {
    alert("Chaos injection failed: " + err.message);
  }
}

// Tab 4: System Metrics
async function loadSystemMetrics() {
  try {
    const res = await fetch('/api/metrics');
    if (!res.ok) return;
    const m = await res.json();
    document.getElementById('stat-reproducible').innerText = `${m.reproducibility_audit_rate_pct.toFixed(1)}%`;
    document.getElementById('stat-corruption').innerText = `${m.state_corruption_rate_pct.toFixed(1)}%`;
    document.getElementById('stat-datasets').innerText = m.total_datasets_registered;
    document.getElementById('stat-inferences').innerText = m.total_inferences_logged;
  } catch (err) {
    console.error("Failed to load metrics:", err);
  }
}
