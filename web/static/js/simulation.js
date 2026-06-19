/* simulation.js — Simulation Lab interactive logic */
'use strict';

// ── Constants ──────────────────────────────────────────────────────────────────
const PROCESS_STEPS = [
  { id: 'read-hr',     label: 'Reading heart rate (MAX30102)',          comp: 'max30102' },
  { id: 'read-temp',   label: 'Reading body temperature (DS18B20)',     comp: 'ds18b20'  },
  { id: 'read-co',     label: 'Reading CO level (MQ-7)',                comp: 'mq7'      },
  { id: 'read-imu',    label: 'Reading IMU / fall state (MPU6050)',     comp: 'mpu6050'  },
  { id: 'esp32-proc',  label: 'ESP32 processing readings',              comp: 'esp32'    },
  { id: 'classify',    label: 'Classifying status: OK / WARN / DANGER', comp: 'esp32'   },
  { id: 'oled-update', label: 'Updating OLED display',                  comp: 'oled'    },
  { id: 'alert-out',   label: 'Setting LEDs and Buzzer',                comp: 'leds'    },
  { id: 'mqtt-pub',    label: 'Publishing MQTT payload',                comp: 'mqtt'    },
  { id: 'api-recv',    label: 'FastAPI receives telemetry',             comp: 'api'     },
  { id: 'dash-update', label: 'Dashboard WebSocket broadcast',          comp: 'dash'    },
  { id: 'csv-write',   label: 'Logger writes CSV record',               comp: 'logger'  },
  { id: 'report-tick', label: 'Report counters updated',                comp: 'report'  },
];

const STEP_DETAILS = {
  'read-hr':     'MAX30102 pulse oximeter sensor sampled via I2C bus (GPIO21/22). Heart rate value extracted.',
  'read-temp':   'DS18B20 one-wire temperature sensor polled on GPIO4. Body temperature converted to \xB0C.',
  'read-co':     'MQ-7 CO sensor analog output read on GPIO34 (ADC). Value converted to ppm concentration.',
  'read-imu':    'MPU6050 6-DOF IMU queried via I2C. Accelerometer data analysed for fall/incapacitation.',
  'esp32-proc':  'All four sensor values assembled into a readings dictionary for classification.',
  'classify':    'Threshold evaluation: HR > 130 → DANGER; Temp > 39.5 → DANGER; CO > 200 → DANGER. Fall → highest priority.',
  'oled-update': 'SSD1306 OLED updated with current status string and alert message via I2C (GPIO21/22).',
  'alert-out':   'LED outputs set: GPIO27=green, GPIO26=yellow, GPIO25=red. Buzzer on GPIO18 set to OFF/SLOW/FAST.',
  'mqtt-pub':    'JSON payload serialised and published to broker.emqx.io:1883 on topic smart_firefighter/ff01/telemetry (QoS 1).',
  'api-recv':    'FastAPI simulation_manager broadcasts payload via asyncio to all WebSocket subscribers.',
  'dash-update': 'Browser WebSocket receives JSON and updates cards, charts, and status badge in real time.',
  'csv-write':   'SimulationManager appends record to web_telemetry_*.csv in data/logs/ for offline analysis.',
  'report-tick': 'Session counters (total, warning, danger, fall) incremented. Visible in /api/status endpoint.',
};

// ── State ──────────────────────────────────────────────────────────────────────
let currentStep  = -1;
let cycleCount   = 0;
let lastPayload  = null;
let playbackMode = 'stopped'; // 'running' | 'paused' | 'step' | 'stopped'
let stepTimer    = null;
const stepInterval = 700;
let wsLocal      = null;

// ── DOM helpers ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const qsa = sel => document.querySelectorAll(sel);
function setText(id, val) { const el = $(id); if (el) el.textContent = val; }

// ── Debug log ──────────────────────────────────────────────────────────────────
function simLog(msg) {
  console.log('[SimLab]', msg);
  const panel = $('debug-log');
  if (!panel) return;
  const line = document.createElement('div');
  const ts = new Date().toISOString().split('T')[1].slice(0, 12);
  line.textContent = ts + ' ' + msg;
  panel.insertBefore(line, panel.firstChild);
  while (panel.children.length > 30) panel.removeChild(panel.lastChild);
}

// ── WebSocket ──────────────────────────────────────────────────────────────────
function initSimWS() {
  const url = 'ws://' + location.host + '/ws/telemetry';
  simLog('WS connecting to ' + url);
  wsLocal = new WebSocket(url);

  wsLocal.onopen = () => {
    setWsDot(true);
    simLog('WS connected');
  };

  wsLocal.onmessage = ev => {
    try {
      const p = JSON.parse(ev.data);
      if (p.type === 'ping') return;
      lastPayload = p;
      simLog('WS payload: status=' + p.status + ' hr=' + p.heart_rate);
      onPayloadReceived(p);
    } catch (e) {
      simLog('WS parse error: ' + e.message);
    }
  };

  wsLocal.onclose = () => {
    setWsDot(false);
    simLog('WS closed, reconnecting in 3s...');
    setTimeout(initSimWS, 3000);
  };

  wsLocal.onerror = () => {
    simLog('WS error');
    wsLocal.close();
  };
}

function setWsDot(connected) {
  qsa('.ws-dot').forEach(d => d.classList.toggle('connected', connected));
  qsa('.ws-label').forEach(el => {
    el.textContent = connected ? 'Live' : 'Reconnecting...';
  });
}

// ── Payload received ───────────────────────────────────────────────────────────
function onPayloadReceived(p) {
  updateComponentCards(p);
  updateAlertPanel(p);
  updateCommunicationPanel(p);
  updateJsonDisplay(p);
  updateCircuitState(p);
  pollStatusNow();

  if (playbackMode === 'running') {
    // Only start a new cycle if none is currently in progress.
    // If a cycle is running, the fresh data is already shown above;
    // advanceStep() will auto-restart with lastPayload when it finishes.
    const cycleIdle = currentStep < 0 || currentStep >= PROCESS_STEPS.length;
    if (cycleIdle) startStepCycle(p);
  } else if (playbackMode === 'stopped' || playbackMode === 'paused') {
    highlightAllDone();
  }
}

// ── Process flow step cycling ──────────────────────────────────────────────────
function startStepCycle(payload) {
  clearTimeout(stepTimer);
  currentStep = 0;
  advanceStep(payload);
}

function advanceStep(payload) {
  if (currentStep >= PROCESS_STEPS.length) {
    cycleCount++;
    setText('sim-cycle-count', 'Cycle #' + cycleCount);
    clearTimeout(stepTimer);
    if (playbackMode === 'running') {
      // Auto-restart immediately with the latest received payload
      currentStep = 0;
      stepTimer = setTimeout(() => advanceStep(lastPayload || payload), stepInterval);
    } else {
      currentStep = -1;
    }
    return;
  }
  renderStep(currentStep);
  currentStep++;
  if (playbackMode === 'running') {
    stepTimer = setTimeout(() => advanceStep(payload), stepInterval);
  }
}

function renderStep(idx) {
  const steps = qsa('.ps-step');
  steps.forEach((el, i) => {
    el.classList.remove('ps-active', 'ps-done');
    if (i < idx) el.classList.add('ps-done');
    if (i === idx) el.classList.add('ps-active');
  });

  const step = PROCESS_STEPS[idx];
  if (!step) return;

  setText('sim-step-name', step.label);
  const detailBox = $('step-detail-box');
  if (detailBox) {
    detailBox.innerHTML = '<strong>' + step.label + '</strong><br>' + (STEP_DETAILS[step.id] || '');
  }
  highlightCircuitComponent(step.comp);
}

function highlightAllDone() {
  qsa('.ps-step').forEach(el => {
    el.classList.remove('ps-active');
    el.classList.add('ps-done');
  });
  setText('sim-step-name', 'Simulation stopped');
}

// ── Manual next-step ───────────────────────────────────────────────────────────
function stepOnce() {
  clearTimeout(stepTimer);
  if (!lastPayload) {
    const scenario = getScenario();
    simLog('Step: no payload yet, triggering publish-once for ' + scenario);
    apiPost('/api/simulation/publish-once', { scenario }).then(p => {
      if (p && p.status) {
        lastPayload = p;
        onPayloadReceived(p);
        showSimToast('Step: ' + p.status);
      } else {
        showSimToast('Step failed — is the server running?', 'error');
      }
    });
    return;
  }
  if (currentStep < 0 || currentStep >= PROCESS_STEPS.length) currentStep = 0;
  renderStep(currentStep);
  currentStep++;
  if (currentStep >= PROCESS_STEPS.length) currentStep = 0;
}

// ── Playback controls ──────────────────────────────────────────────────────────
async function simStart() {
  const scenario = getScenario();
  simLog('Start clicked, scenario=' + scenario);

  const res = await apiPost('/api/simulation/start', { scenario });
  simLog('Start API response: ' + JSON.stringify(res));

  if (!res || res.status !== 'started') {
    showSimToast('Failed to start — check server console.', 'error');
    return;
  }

  playbackMode = 'running';
  updatePlaybackButtons();
  showSimToast('Simulation started: ' + scenario, 'success');
  pollStatusNow();
}

function simPause() {
  if (playbackMode === 'running') {
    playbackMode = 'paused';
    clearTimeout(stepTimer);
  } else if (playbackMode === 'paused') {
    playbackMode = 'running';
    if (lastPayload) {
      if (currentStep < 0 || currentStep >= PROCESS_STEPS.length) currentStep = 0;
      advanceStep(lastPayload);
    }
  }
  updatePlaybackButtons();
  simLog('Pause toggled, mode=' + playbackMode);
}

async function simStop() {
  simLog('Stop clicked');
  const res = await apiPost('/api/simulation/stop', {});
  simLog('Stop API response: ' + JSON.stringify(res));

  playbackMode = 'stopped';
  clearTimeout(stepTimer);
  currentStep = -1;
  updatePlaybackButtons();
  qsa('.ps-step').forEach(el => el.classList.remove('ps-active', 'ps-done'));
  setText('sim-step-name', 'Stopped');
  highlightCircuitComponent(null);
  pollStatusNow();
}

function simReset() {
  simStop();
  cycleCount = 0;
  setText('sim-cycle-count', 'Cycle #0');
  updateJsonDisplay(null);
  resetCircuitState();
  resetAlertPanel();
  resetCommunicationPanel();
  resetComponentCards();
  simLog('Reset');
}

function simPublishOnce() {
  const scenario = getScenario();
  simLog('PublishOnce, scenario=' + scenario);
  apiPost('/api/simulation/publish-once', { scenario }).then(p => {
    if (p && p.status) showSimToast('Published: ' + p.status);
    simLog('PublishOnce response: ' + JSON.stringify(p));
  });
}

function updatePlaybackButtons() {
  const running = playbackMode === 'running';
  const paused  = playbackMode === 'paused';
  const stopped = playbackMode === 'stopped';

  const btnStart = $('sim-btn-start');
  const btnPause = $('sim-btn-pause');
  const btnStop  = $('sim-btn-stop');

  if (btnStart) btnStart.disabled = running || paused;
  if (btnPause) {
    btnPause.disabled = stopped;
    btnPause.textContent = paused ? 'Resume' : '❚❚ Pause';
  }
  if (btnStop) btnStop.disabled = stopped;
}

function getScenario() {
  const sel = $('sim-scenario-select');
  return sel ? sel.value : 'normal';
}

// ── API helpers ────────────────────────────────────────────────────────────────
async function apiPost(url, body) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const txt = await res.text();
      simLog('API POST ' + url + ' -> HTTP ' + res.status + ': ' + txt);
      showSimToast('Server error ' + res.status, 'error');
      return null;
    }
    return await res.json();
  } catch (e) {
    simLog('API POST ' + url + ' network error: ' + e.message);
    showSimToast('Network error: ' + e.message, 'error');
    return null;
  }
}

async function apiGet(url) {
  try {
    const res = await fetch(url);
    return await res.json();
  } catch (e) {
    simLog('API GET ' + url + ' failed: ' + e.message);
    return null;
  }
}

// ── Status polling ─────────────────────────────────────────────────────────────
function pollStatusNow() {
  apiGet('/api/status').then(data => {
    if (!data) return;
    setText('sim-total',  data.total_readings);
    setText('sim-warn',   data.warning_count);
    setText('sim-danger', data.danger_count);
    setText('sim-fall',   data.fall_count);

    const ind = $('sim-running-ind');
    if (ind) {
      ind.className = 'sim-status-indicator ' + (data.simulation_running ? 'running' : 'stopped');
      const txt = $('sim-running-text');
      if (txt) txt.textContent = data.simulation_running
        ? 'Running: ' + data.active_scenario
        : 'Stopped';
    }
  });
}

// ── Component card updates ─────────────────────────────────────────────────────
function updateComponentCards(p) {
  setCompCard('card-max30102', p.heart_rate != null ? p.heart_rate.toFixed(1) : '--', getStatusColorClass(p.status));
  setText('compval-hr', p.heart_rate != null ? p.heart_rate.toFixed(1) : '--');

  setCompCard('card-ds18b20', p.body_temp != null ? p.body_temp.toFixed(1) : '--', tempColorClass(p.body_temp));
  setText('compval-temp', p.body_temp != null ? p.body_temp.toFixed(1) : '--');

  setCompCard('card-mq7', p.co_level != null ? p.co_level.toFixed(1) : '--', coColorClass(p.co_level));
  setText('compval-co', p.co_level != null ? p.co_level.toFixed(1) : '--');

  const fallText = p.fall_detected ? 'FALL!' : 'Normal';
  setCompCard('card-mpu6050', fallText, p.fall_detected ? 'active-purple' : 'active-green');
  setText('compval-fall', fallText);

  const ledColor = LED_MAP[p.status] || 'off';
  setText('compval-oled',  OLED_MAP[p.status]   || p.status || '--');
  setText('compval-buzzer', BUZZER_MAP[p.status] || 'OFF');
  setText('compval-led-g', ledColor === 'green'  ? 'ON' : 'OFF');
  setText('compval-led-y', ledColor === 'yellow' ? 'ON' : 'OFF');
  setText('compval-led-r', (ledColor === 'red' || ledColor === 'purple') ? 'ON' : 'OFF');

  setCompCard('card-oled',  OLED_MAP[p.status] || p.status || '--', 'active');
  setCompCard('card-buzzer', BUZZER_MAP[p.status] || 'OFF', p.status === 'OK' ? '' : 'active-orange');
  setCompCard('card-led-g', ledColor === 'green'  ? 'ON' : 'off', ledColor === 'green'  ? 'active-green'  : '');
  setCompCard('card-led-y', ledColor === 'yellow' ? 'ON' : 'off', ledColor === 'yellow' ? 'active-yellow' : '');
  setCompCard('card-led-r', (ledColor === 'red' || ledColor === 'purple') ? 'ON' : 'off',
    (ledColor === 'red' || ledColor === 'purple') ? 'active-red' : '');
}

function setCompCard(cardId, value, colorClass) {
  const card = $(cardId);
  if (!card) return;
  const valEl = card.querySelector('.comp-card-value');
  if (valEl) valEl.textContent = value;
  card.className = 'comp-card' + (colorClass ? ' ' + colorClass : '');
}

function resetComponentCards() {
  qsa('.comp-card').forEach(c => c.className = 'comp-card');
  qsa('.comp-card-value').forEach(v => v.textContent = '--');
  qsa('[id^="compval-"]').forEach(v => v.textContent = '--');
}

function getStatusColorClass(status) {
  return { OK: 'active-green', WARNING: 'active-yellow', DANGER: 'active-red', FALL_DETECTED: 'active-purple' }[status] || 'active';
}
function tempColorClass(v) {
  if (v == null) return '';
  if (v > 39.5)  return 'active-red';
  if (v >= 38.0) return 'active-yellow';
  return 'active-green';
}
function coColorClass(v) {
  if (v == null) return '';
  if (v > 200)  return 'active-red';
  if (v >= 50)  return 'active-yellow';
  return 'active-green';
}

// ── Alert panel ────────────────────────────────────────────────────────────────
const LED_MAP    = { OK: 'green', WARNING: 'yellow', DANGER: 'red', FALL_DETECTED: 'red' };
const BUZZER_MAP = { OK: 'OFF', WARNING: 'SLOW BEEP', DANGER: 'FAST BEEP', FALL_DETECTED: 'FAST BEEP' };
const OLED_MAP   = { OK: 'STATUS OK', WARNING: 'WARNING', DANGER: 'DANGER', FALL_DETECTED: 'FALL DETECTED' };

function updateAlertPanel(p) {
  const ledColor = LED_MAP[p.status] || '';
  const bzCls  = { OK: '', WARNING: 'bz-slow', DANGER: 'bz-fast', FALL_DETECTED: 'bz-fast' }[p.status] || '';
  const oledCls = { OK: 'oled-ok', WARNING: 'oled-warn', DANGER: 'oled-danger', FALL_DETECTED: 'oled-fall' }[p.status] || '';

  ['green', 'yellow', 'red'].forEach(c => {
    const el = $('sim-led-' + c);
    if (el) el.className = 'sim-led' + (ledColor === c ? ' sim-led-' + c : '');
  });
  setText('alert-led-state', ledColor ? ledColor.toUpperCase() + ' LED' : 'ALL OFF');

  const bz = $('sim-buzzer');
  if (bz) bz.className = 'sim-buzzer' + (bzCls ? ' ' + bzCls : '');
  setText('alert-bz-state', BUZZER_MAP[p.status] || 'OFF');

  const oled = $('sim-oled');
  if (oled) {
    oled.className = 'sim-oled' + (oledCls ? ' ' + oledCls : '');
    const msgLine = oled.querySelector('.oled-msg');
    const ffLine  = oled.querySelector('.oled-ff-line');
    if (msgLine) msgLine.textContent = OLED_MAP[p.status] || p.status;
    if (ffLine)  ffLine.textContent  = p.firefighter_id || 'FF-01';
  }
}

function resetAlertPanel() {
  ['green', 'yellow', 'red'].forEach(c => {
    const el = $('sim-led-' + c);
    if (el) el.className = 'sim-led';
  });
  const bz = $('sim-buzzer');
  if (bz) bz.className = 'sim-buzzer';
  const oled = $('sim-oled');
  if (oled) {
    oled.className = 'sim-oled';
    const msgLine = oled.querySelector('.oled-msg');
    if (msgLine) msgLine.textContent = 'STANDBY';
    const ffLine = oled.querySelector('.oled-ff-line');
    if (ffLine) ffLine.textContent = '';
  }
  setText('alert-led-state', 'ALL OFF');
  setText('alert-bz-state', 'OFF');
}

// ── Communication flow panel ───────────────────────────────────────────────────
let commAnimTimer = null;

function updateCommunicationPanel(p) {
  clearTimeout(commAnimTimer);
  const nodes  = ['cn-wearable', 'cn-mqtt', 'cn-dashboard', 'cn-logger'];
  const arrows = ['ca-1', 'ca-2', 'ca-3'];
  nodes.forEach(id => { const el = $(id); if (el) el.classList.remove('cn-active'); });
  arrows.forEach(id => {
    const el = $(id);
    if (el) {
      const line = el.querySelector('.comm-arrow-line');
      const head = el.querySelector('.comm-arrow-head');
      if (line) line.classList.remove('pulsing');
      if (head) head.classList.remove('active');
    }
  });

  const seq = [
    [0,    'cn-wearable'],
    [350,  'ca-1', true],
    [600,  'cn-mqtt'],
    [950,  'ca-2', true],
    [1200, 'cn-dashboard'],
    [1450, 'ca-3', true],
    [1700, 'cn-logger'],
  ];
  seq.forEach(([delay, id, isArrow]) => {
    commAnimTimer = setTimeout(() => {
      const el = $(id);
      if (!el) return;
      if (isArrow) {
        const line = el.querySelector('.comm-arrow-line');
        const head = el.querySelector('.comm-arrow-head');
        if (line) line.classList.add('pulsing');
        if (head) head.classList.add('active');
        setTimeout(() => {
          if (line) line.classList.remove('pulsing');
          if (head) head.classList.remove('active');
        }, 700);
      } else {
        el.classList.add('cn-active');
      }
    }, delay);
  });

  setText('comm-topic', p.status ? 'Status: ' + p.status : '');
  setText('comm-ts', p.timestamp ? (p.timestamp.split('T')[1] || '').replace('Z', '') : '');

  const badge = $('comm-live-badge');
  if (badge) {
    badge.textContent = 'LIVE';
    badge.className = 'comm-status-badge live';
    setTimeout(() => {
      if (badge) { badge.textContent = 'idle'; badge.className = 'comm-status-badge'; }
    }, 2500);
  }
}

function resetCommunicationPanel() {
  clearTimeout(commAnimTimer);
  ['cn-wearable', 'cn-mqtt', 'cn-dashboard', 'cn-logger'].forEach(id => {
    const el = $(id); if (el) el.classList.remove('cn-active');
  });
  setText('comm-topic', '');
  setText('comm-ts', '');
}

// ── JSON display ───────────────────────────────────────────────────────────────
function updateJsonDisplay(p) {
  const pre = $('json-display');
  if (!pre) return;
  if (!p) { pre.textContent = '{ awaiting data... }'; return; }
  const lines = JSON.stringify(p, null, 2).split('\n');
  pre.innerHTML = lines.map(line =>
    line
      .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
      .replace(/: "([^"]*)"/g, ': <span class="json-str">"$1"</span>')
      .replace(/: (true|false)/g, ': <span class="json-bool">$1</span>')
      .replace(/: (-?\d+\.?\d*)/g, ': <span class="json-num">$1</span>')
  ).join('\n');
}

// ── Circuit SVG component highlighting ────────────────────────────────────────
const CIRCUIT_COMP_MAP = {
  max30102: ['circ-max30102'],
  ds18b20:  ['circ-ds18b20'],
  mq7:      ['circ-mq7'],
  mpu6050:  ['circ-mpu6050'],
  esp32:    ['circ-esp32'],
  oled:     ['circ-oled'],
  leds:     ['circ-led-green', 'circ-led-yellow', 'circ-led-red', 'circ-buzzer'],
  mqtt:     ['circ-mqtt-cloud'],
  api:      ['circ-api-box'],
  dash:     ['circ-dash-box'],
  logger:   ['circ-log-box'],
};

const WIRE_MAP = {
  max30102: ['wire-sda-left', 'wire-scl-left'],
  ds18b20:  ['wire-1wire'],
  mq7:      ['wire-adc'],
  mpu6050:  ['wire-sda-left', 'wire-scl-left'],
  esp32:    [],
  oled:     ['wire-sda-right', 'wire-scl-right'],
  leds:     ['wire-led-g', 'wire-led-y', 'wire-led-r', 'wire-buzzer'],
};

function highlightCircuitComponent(compKey) {
  qsa('[id^="circ-"]').forEach(el => el.removeAttribute('filter'));
  qsa('[id^="wire-"]').forEach(el => {
    el.setAttribute('stroke-opacity', '0.35');
    el.setAttribute('stroke-width', el.dataset.baseWidth || '1.5');
    el.removeAttribute('stroke-dasharray');
    el.classList.remove('wire-flowing');
  });

  if (!compKey) return;

  const compIds = CIRCUIT_COMP_MAP[compKey] || [];
  compIds.forEach(id => {
    const el = $(id);
    if (el) el.setAttribute('filter', 'url(#glow-active)');
  });

  const wireIds = WIRE_MAP[compKey] || [];
  wireIds.forEach(id => {
    const el = $(id);
    if (el) {
      el.setAttribute('stroke-opacity', '1');
      el.setAttribute('stroke-width', ((parseFloat(el.dataset.baseWidth) || 1.5) + 1).toString());
      el.setAttribute('stroke-dasharray', '8 4');
      el.classList.add('wire-flowing');
    }
  });
}

function updateCircuitState(p) {
  const setsvg = (id, val) => { const el = $(id); if (el) el.textContent = val; };
  setsvg('svgval-hr',     p.heart_rate != null ? p.heart_rate.toFixed(1) + ' BPM' : '--');
  setsvg('svgval-temp',   p.body_temp  != null ? p.body_temp.toFixed(1)  + ' \xB0C'   : '--');
  setsvg('svgval-co',     p.co_level   != null ? p.co_level.toFixed(1)   + ' ppm' : '--');
  setsvg('svgval-fall',   p.fall_detected ? 'FALL!' : 'Normal');
  setsvg('svgval-oled',   OLED_MAP[p.status] || p.status || '--');
  setsvg('svgval-status', p.status || '--');

  const ledColor = LED_MAP[p.status] || '';
  const ledElG = $('svgled-green');
  const ledElY = $('svgled-yellow');
  const ledElR = $('svgled-red');
  if (ledElG) ledElG.setAttribute('fill', ledColor === 'green'  ? '#22c55e' : '#1f2937');
  if (ledElY) ledElY.setAttribute('fill', ledColor === 'yellow' ? '#eab308' : '#1f2937');
  if (ledElR) ledElR.setAttribute('fill', (ledColor === 'red' || ledColor === 'purple') ? '#ef4444' : '#1f2937');

  const gledEl = $('circ-led-green');
  const yledEl = $('circ-led-yellow');
  const rledEl = $('circ-led-red');
  if (gledEl) gledEl.setAttribute('filter', ledColor === 'green'  ? 'url(#glow-led)' : '');
  if (yledEl) yledEl.setAttribute('filter', ledColor === 'yellow' ? 'url(#glow-led)' : '');
  if (rledEl) rledEl.setAttribute('filter', (ledColor === 'red' || ledColor === 'purple') ? 'url(#glow-led)' : '');

  const oledScreen = $('svg-oled-screen');
  if (oledScreen) {
    const c = { OK: '#4ade80', WARNING: '#fbbf24', DANGER: '#f87171', FALL_DETECTED: '#c084fc' };
    oledScreen.setAttribute('fill', c[p.status] || '#1a3a5e');
  }
}

function resetCircuitState() {
  ['svgval-hr', 'svgval-temp', 'svgval-co', 'svgval-fall', 'svgval-oled', 'svgval-status'].forEach(id => {
    const el = $(id); if (el) el.textContent = '--';
  });
  const ledElG = $('svgled-green');
  const ledElY = $('svgled-yellow');
  const ledElR = $('svgled-red');
  if (ledElG) ledElG.setAttribute('fill', '#1f2937');
  if (ledElY) ledElY.setAttribute('fill', '#1f2937');
  if (ledElR) ledElR.setAttribute('fill', '#1f2937');
  ['circ-led-green', 'circ-led-yellow', 'circ-led-red'].forEach(id => {
    const el = $(id); if (el) el.removeAttribute('filter');
  });
  const oledScreen = $('svg-oled-screen');
  if (oledScreen) oledScreen.setAttribute('fill', '#0a1628');
  highlightCircuitComponent(null);
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function showSimToast(msg, type) {
  const container = $('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast ' + (type || '');
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Wiring table toggle ────────────────────────────────────────────────────────
function toggleWiringTable() {
  const wrap = $('wiring-table-wrap');
  const btn  = $('wiring-toggle-btn');
  if (!wrap) return;
  wrap.classList.toggle('open');
  if (btn) btn.textContent = wrap.classList.contains('open') ? '▲ Hide Wiring Reference' : '▼ Show Wiring Reference';
}

// ── Boot ───────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  simLog('Simulation Lab loaded');
  initSimWS();
  updatePlaybackButtons();
  buildProcessStepsList();
  pollStatusNow();

  const on = (id, fn) => { const el = $(id); if (el) el.addEventListener('click', fn); };
  on('sim-btn-start',    simStart);
  on('sim-btn-pause',    simPause);
  on('sim-btn-stop',     simStop);
  on('sim-btn-reset',    simReset);
  on('sim-btn-step',     stepOnce);
  on('sim-btn-pub-once', simPublishOnce);
  on('wiring-toggle-btn', toggleWiringTable);

  const scenSel = $('sim-scenario-select');
  if (scenSel) scenSel.addEventListener('change', () => {
    simLog('Scenario changed to ' + getScenario());
    if (playbackMode === 'running') {
      apiPost('/api/simulation/set-scenario', { scenario: getScenario() });
    }
  });

  setInterval(pollStatusNow, 5000);
});

function buildProcessStepsList() {
  const container = $('process-steps-list');
  if (!container) return;
  container.innerHTML = '';
  PROCESS_STEPS.forEach((step, idx) => {
    const div = document.createElement('div');
    div.className = 'ps-step';
    div.id = 'ps-' + step.id;
    div.innerHTML =
      '<div class="ps-num">' + (idx + 1) + '</div>' +
      '<span class="ps-label">' + step.label + '</span>';
    container.appendChild(div);
  });
}
