/* app.js — Smart Firefighter Web Dashboard
   Handles WebSocket connection, live card updates, Chart.js charts,
   event log table, and simulation control API calls.
*/

// ── WebSocket ─────────────────────────────────────────────────────────────────
let ws = null;
let wsReconnectTimer = null;
const WS_URL = `ws://${location.host}/ws/telemetry`;

function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setWsDot(true);
    clearTimeout(wsReconnectTimer);
  };

  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'ping') return;
      handlePayload(payload);
    } catch (_) {}
  };

  ws.onclose = () => {
    setWsDot(false);
    wsReconnectTimer = setTimeout(connectWS, 3000);
  };

  ws.onerror = () => ws.close();
}

function setWsDot(connected) {
  document.querySelectorAll('.ws-dot').forEach(d => {
    d.classList.toggle('connected', connected);
  });
  document.querySelectorAll('.ws-label').forEach(el => {
    el.textContent = connected ? 'Live' : 'Reconnecting...';
  });
}

// ── Chart.js setup ────────────────────────────────────────────────────────────
const MAX_POINTS = 40;
const chartData = {
  labels: [],
  hr:   [],
  temp: [],
  co:   [],
};

let hrChart, tempChart, coChart;

function initCharts() {
  const defaults = {
    type: 'line',
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 6, font: { size: 10 } }, grid: { color: '#f1f5f9' } },
        y: { ticks: { font: { size: 10 } }, grid: { color: '#f1f5f9' } },
      },
    },
  };

  const el = id => document.getElementById(id);

  hrChart = new Chart(el('chart-hr'), {
    ...defaults,
    data: {
      labels: chartData.labels,
      datasets: [{
        data: chartData.hr,
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37,99,235,.08)',
        borderWidth: 2,
        pointRadius: 2,
        fill: true,
        tension: .35,
      }],
    },
    options: {
      ...defaults.options,
      scales: {
        ...defaults.options.scales,
        y: { ...defaults.options.scales.y, min: 40, max: 200,
          ticks: { font: { size: 10 } }, grid: { color: '#f1f5f9' } },
      },
    },
  });

  tempChart = new Chart(el('chart-temp'), {
    ...defaults,
    data: {
      labels: chartData.labels,
      datasets: [{
        data: chartData.temp,
        borderColor: '#dc2626',
        backgroundColor: 'rgba(220,38,38,.08)',
        borderWidth: 2,
        pointRadius: 2,
        fill: true,
        tension: .35,
      }],
    },
    options: {
      ...defaults.options,
      scales: {
        ...defaults.options.scales,
        y: { ...defaults.options.scales.y, min: 35, max: 42,
          ticks: { font: { size: 10 } }, grid: { color: '#f1f5f9' } },
      },
    },
  });

  coChart = new Chart(el('chart-co'), {
    ...defaults,
    data: {
      labels: chartData.labels,
      datasets: [{
        data: chartData.co,
        borderColor: '#f97316',
        backgroundColor: 'rgba(249,115,22,.08)',
        borderWidth: 2,
        pointRadius: 2,
        fill: true,
        tension: .35,
      }],
    },
    options: {
      ...defaults.options,
      scales: {
        ...defaults.options.scales,
        y: { ...defaults.options.scales.y, min: 0, max: 500,
          ticks: { font: { size: 10 } }, grid: { color: '#f1f5f9' } },
      },
    },
  });
}

function pushChartPoint(payload) {
  const label = payload.timestamp
    ? payload.timestamp.split('T')[1].replace('Z', '')
    : '';
  chartData.labels.push(label);
  chartData.hr.push(payload.heart_rate);
  chartData.temp.push(payload.body_temp);
  chartData.co.push(payload.co_level);

  if (chartData.labels.length > MAX_POINTS) {
    chartData.labels.shift();
    chartData.hr.shift();
    chartData.temp.shift();
    chartData.co.shift();
  }
  hrChart.update();
  tempChart.update();
  coChart.update();
}

// ── Status helpers ────────────────────────────────────────────────────────────
const STATUS_CLASSES = {
  OK: 'ok', WARNING: 'warning', DANGER: 'danger', FALL_DETECTED: 'fall',
};

function statusClass(s) { return STATUS_CLASSES[s] || ''; }

const LED_MAP = {
  OK: 'green', WARNING: 'yellow', DANGER: 'red', FALL_DETECTED: 'red',
};
const BUZZER_MAP = {
  OK: { cls: '', text: 'OFF' },
  WARNING: { cls: 'slow', text: 'SLOW BEEP' },
  DANGER:  { cls: 'fast', text: 'FAST BEEP' },
  FALL_DETECTED: { cls: 'fast', text: 'FAST BEEP' },
};
const OLED_MAP = {
  OK: 'STATUS OK', WARNING: 'WARNING', DANGER: 'DANGER', FALL_DETECTED: 'FALL DETECTED',
};

// ── Payload handler ───────────────────────────────────────────────────────────
const MAX_LOG_ROWS = 50;

function handlePayload(p) {
  // Telemetry cards
  setText('val-hr',    p.heart_rate   != null ? p.heart_rate.toFixed(1)  : '--');
  setText('val-temp',  p.body_temp    != null ? p.body_temp.toFixed(1)   : '--');
  setText('val-co',    p.co_level     != null ? p.co_level.toFixed(1)    : '--');
  setText('val-fall',  p.fall_detected ? 'YES' : 'No');
  setText('val-ts',    p.timestamp || '--');
  setText('val-alert', p.alert_message || '');

  // Status badge
  const statusEl = document.getElementById('val-status');
  if (statusEl) {
    statusEl.textContent = p.status || '--';
    statusEl.className = 'status-badge status-' + (p.status || 'unknown');
  }

  // Card border colors
  const sc = statusClass(p.status);
  document.querySelectorAll('.tele-card').forEach(c => {
    c.className = 'tele-card ' + sc;
  });

  // System flow highlight
  document.querySelectorAll('.flow-node').forEach(n => n.classList.add('active'));

  // Local alert panel
  const led = document.getElementById('led-indicator');
  if (led) {
    led.className = 'led ' + (LED_MAP[p.status] || '');
  }
  const buzzer = document.getElementById('buzzer-ring');
  const buzzerText = document.getElementById('buzzer-text');
  if (buzzer) {
    const bz = BUZZER_MAP[p.status] || { cls: '', text: 'OFF' };
    buzzer.className = 'buzzer-ring ' + bz.cls;
    if (buzzerText) buzzerText.textContent = bz.text;
  }
  const oled = document.getElementById('oled-screen');
  if (oled) oled.textContent = OLED_MAP[p.status] || p.status;

  // Charts
  if (hrChart) pushChartPoint(p);

  // Event log table
  prependLogRow(p);
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function prependLogRow(p) {
  const tbody = document.getElementById('log-tbody');
  if (!tbody) return;

  const sc = statusClass(p.status);
  const row = document.createElement('tr');
  row.className = sc ? `row-${sc}` : '';
  row.innerHTML = [
    td(p.timestamp || ''),
    td(p.firefighter_id || ''),
    td(p.heart_rate   != null ? p.heart_rate.toFixed(1)  : ''),
    td(p.body_temp    != null ? p.body_temp.toFixed(1)   : ''),
    td(p.co_level     != null ? p.co_level.toFixed(1)    : ''),
    td(p.fall_detected ? 'YES' : 'No'),
    `<td><span class="status-badge status-${p.status || 'unknown'}">${p.status || ''}</span></td>`,
    td(p.alert_message || ''),
  ].join('');

  tbody.insertBefore(row, tbody.firstChild);

  // Trim to max rows
  while (tbody.children.length > MAX_LOG_ROWS) {
    tbody.removeChild(tbody.lastChild);
  }
}

function td(val) { return `<td>${escHtml(String(val))}</td>`; }
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Simulation control ────────────────────────────────────────────────────────
async function apiCall(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(url, opts);
    return await res.json();
  } catch (err) {
    showToast('Request failed: ' + err.message, 'error');
    return null;
  }
}

function getSelectedScenario() {
  const sel = document.getElementById('scenario-select');
  return sel ? sel.value : 'normal';
}

async function startSim() {
  const scenario = getSelectedScenario();
  const res = await apiCall('POST', '/api/simulation/start', { scenario });
  if (res) {
    showToast('Simulation started: ' + scenario, 'success');
    refreshStatus();
  }
}

async function stopSim() {
  const res = await apiCall('POST', '/api/simulation/stop');
  if (res) {
    showToast('Simulation stopped.', 'success');
    document.querySelectorAll('.flow-node').forEach(n => n.classList.remove('active'));
    refreshStatus();
  }
}

async function publishOnce() {
  const scenario = getSelectedScenario();
  const res = await apiCall('POST', '/api/simulation/publish-once', { scenario });
  if (res && res.status) {
    showToast('Published one reading: ' + res.status);
  }
}

async function changeScenario() {
  const scenario = getSelectedScenario();
  await apiCall('POST', '/api/simulation/set-scenario', { scenario });
}

// ── Status polling ────────────────────────────────────────────────────────────
async function refreshStatus() {
  const data = await apiCall('GET', '/api/status');
  if (!data) return;

  // Simulation status indicator
  const ind = document.getElementById('sim-status-indicator');
  if (ind) {
    ind.className = 'sim-status-indicator ' + (data.simulation_running ? 'running' : 'stopped');
    const txt = document.getElementById('sim-status-text');
    if (txt) txt.textContent = data.simulation_running
      ? 'Running: ' + data.active_scenario
      : 'Stopped';
  }

  // MQTT badge
  const mqttBadge = document.getElementById('badge-mqtt');
  if (mqttBadge) {
    mqttBadge.className = 'badge ' + (data.mqtt_connected ? 'connected' : 'disconnected');
    const v = mqttBadge.querySelector('.value');
    if (v) v.textContent = data.mqtt_connected ? 'Connected' : 'No MQTT';
  }

  // Stats
  setText('stat-total',   data.total_readings);
  setText('stat-warning', data.warning_count);
  setText('stat-danger',  data.danger_count);
  setText('stat-fall',    data.fall_count);

  // Button states
  const btnStart = document.getElementById('btn-start');
  const btnStop  = document.getElementById('btn-stop');
  if (btnStart) btnStart.disabled = data.simulation_running;
  if (btnStop)  btnStop.disabled  = !data.simulation_running;
}

// ── Toast notifications ───────────────────────────────────────────────────────
function showToast(msg, type = '') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Charts (only on index page)
  if (document.getElementById('chart-hr')) initCharts();

  connectWS();
  refreshStatus();
  setInterval(refreshStatus, 5000);

  // Bind buttons
  const on = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener('click', fn); };
  on('btn-start',       startSim);
  on('btn-stop',        stopSim);
  on('btn-publish-once',publishOnce);
  on('scenario-select', changeScenario);
});
