// Mock data generation handles simulation natively
// Visual simulation cues have been removed as requested.
// Core State
const STATE = {
    // Environmental
    temp: "--",
    humidity: "--",

    pressure: "--",
    rain: 0, // 0 = No rain, 1 = Rain

    // Soil Moisture (0-100%)
    soil1: "--",
    soil2: "--",
    soil3: "--",

    // Tank Level (Distance in cm, lower is fuller usually, but we'll map to %)
    tankLevel: "--",

    // Pump Status (false = off, true = on)
    pumps: {
        div1: false,
        div2: false,
        div3: false,
        tank: false
    },
    // Pump Modes
    pump_modes: {
        div1: "AUTO",
        div2: "AUTO",
        div3: "AUTO",
        tank: "AUTO"
    },

    // Security
    pir1: false,
    pir2: false,

    // Light System
    ldr: 0,
    night_leds: [0, 0, 0, 0],
    night_mode: "AUTO", // AUTO, ON, OFF

    buzzers: {
        front: false,
        back: false
    }
};

// Settings State
let SETTINGS = {
    username: 'Admin',
    notifications: true,
    dryThreshold: 30,
    wetThreshold: 70,
    pirSensorEnabled: true
};

let updateInterval;
let chartsInitialized = false;
let chartInstances = {};
let lastPacketTime = 0; // For heartbeat

// Audio Context for Beep Sounds
let audioContext = null;

// Play beep sound using Web Audio API
function playBeep(frequency = 800, duration = 200, type = 'sine') {
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = frequency;
        oscillator.type = type;

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration / 1000);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + duration / 1000);
    } catch (e) {
        console.log("Audio not available:", e);
    }
}

// Play alert beep for motion detection
function playMotionAlert() {
    playBeep(1000, 200, 'square'); // High-pitched alert beep
}

// Stats Logic
let STATS = {
    packets: 0,
    startTime: Date.now(),
    maxTemp: -999,
    minTemp: 999,
    avgSoil: 0,
    log: []
};

function initStats() {
    STATS.startTime = Date.now();
    STATS.packets = 0;
    STATS.maxTemp = -999;
    STATS.minTemp = 999;
    STATS.log = [];
    updateStatsDOM();
}

function updateStats() {
    STATS.packets++;

    // Uptime
    const diff = Math.floor((Date.now() - STATS.startTime) / 1000);
    const m = Math.floor(diff / 60);
    const s = diff % 60;
    const timeStr = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    const uptimeEl = document.getElementById('stat-uptime');
    if (uptimeEl) uptimeEl.innerText = timeStr;

    // Packets
    const packetEl = document.getElementById('stat-packets');
    if (packetEl) packetEl.innerText = STATS.packets;

    // Temp Extremes
    if (typeof STATE.temp === 'number') {
        if (STATE.temp > STATS.maxTemp) STATS.maxTemp = STATE.temp;
        if (STATE.temp < STATS.minTemp) STATS.minTemp = STATE.temp;

        const maxEl = document.getElementById('stat-max-temp');
        if (maxEl) maxEl.innerText = STATS.maxTemp.toFixed(1) + "°C";

        const minEl = document.getElementById('stat-min-temp');
        if (minEl && STATS.minTemp !== 999) minEl.innerText = STATS.minTemp.toFixed(1) + "°C";
    }

    // Avg Soil
    let avg = 0;
    let count = 0;
    if (typeof STATE.soil1 === 'number') { avg += STATE.soil1; count++; }
    if (typeof STATE.soil2 === 'number') { avg += STATE.soil2; count++; }
    if (typeof STATE.soil3 === 'number') { avg += STATE.soil3; count++; }

    if (count > 0) {
        STATS.avgSoil = avg / count;
        const avgEl = document.getElementById('stat-avg-soil');
        if (avgEl) avgEl.innerText = STATS.avgSoil.toFixed(0) + "%";
    }

    // Log Table
    const tbody = document.getElementById('stats-log-body');
    if (tbody) {
        const row = document.createElement('tr');
        const time = new Date().toLocaleTimeString();
        const tVal = typeof STATE.temp === 'number' ? STATE.temp.toFixed(1) : "--";
        const sVal = count > 0 ? (avg / count).toFixed(0) + "%" : "--";

        let status = "OK";
        if (STATE.pir1 || STATE.pir2) status = "⚠ MOTION";
        else if (STATE.rain) status = "☔ RAIN";
        else if (count > 0 && (avg / count) < SETTINGS.dryThreshold) status = "💧 DRY";

        row.innerHTML = `
            <td>${time}</td>
            <td>${tVal}</td>
            <td>${sVal}</td>
            <td>${status}</td>
        `;

        tbody.prepend(row);
        if (tbody.children.length > 20) tbody.lastChild.remove();
    }
}

function updateStatsDOM() {
    // Initial Clear
    const packetEl = document.getElementById('stat-packets');
    if (packetEl) packetEl.innerText = "0";
    const tbody = document.getElementById('stats-log-body');
    if (tbody) tbody.innerHTML = "";
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSettings(); // Load saved settings first
    updateTime();
    setInterval(updateTime, 1000);

    // Auth Check
    const activeSession = sessionStorage.getItem('agro_auth_session');

    if (activeSession) {
        // Restore session
        toggleLoginScreen(false);
        initDashboard();
        setupSimulationToggle();
    } else {
        // Show login
        toggleLoginScreen(true);
    }

    // Login Form Listener
    const loginForm = document.getElementById('login-form');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);
});
// --- Simulation Mode ---
let SIMULATION_MODE = false;
let simulationInterval = null;

function setupSimulationToggle() {
    const toggle = document.getElementById('simulation-toggle');
    const label = document.getElementById('simulation-label');
    if (!toggle) return;
    toggle.checked = SIMULATION_MODE;
    toggle.addEventListener('change', (e) => {
        SIMULATION_MODE = toggle.checked;
        if (SIMULATION_MODE) {
            label.textContent = 'Simulation Mode (ON)';
            startSimulation();
        } else {
            label.textContent = 'Simulation Mode';
            stopSimulation();
        }
    });
}

function startSimulation() {
    stopSimulation();
    // Immediately update once
    simulateSensorData();
    simulationInterval = setInterval(simulateSensorData, 2000);
}

function stopSimulation() {
    if (simulationInterval) clearInterval(simulationInterval);
    simulationInterval = null;
}

function simulateSensorData() {
    // Generate random but plausible values
    STATE.temp = +(20 + Math.random() * 10).toFixed(1); // 20-30°C
    STATE.humidity = +(40 + Math.random() * 40).toFixed(0); // 40-80%
    STATE.pressure = +(990 + Math.random() * 20).toFixed(0); // 990-1010 hPa
    STATE.rain = Math.random() < 0.2 ? 1 : 0;
    STATE.soil1 = +(30 + Math.random() * 40).toFixed(0); // 30-70%
    STATE.soil2 = +(30 + Math.random() * 40).toFixed(0);
    STATE.soil3 = +(30 + Math.random() * 40).toFixed(0);
    STATE.tankLevel = +(Math.random() * 100).toFixed(0); // 0-100%
    STATE.pumps.div1 = Math.random() < 0.5;
    STATE.pumps.div2 = Math.random() < 0.5;
    STATE.pumps.div3 = Math.random() < 0.5;
    STATE.pumps.tank = Math.random() < 0.5;
    STATE.pump_modes.div1 = 'AUTO';
    STATE.pump_modes.div2 = 'AUTO';
    STATE.pump_modes.div3 = 'AUTO';
    STATE.pump_modes.tank = 'AUTO';
    STATE.pir1 = Math.random() < 0.1;
    STATE.pir2 = Math.random() < 0.1;
    STATE.ldr = +(Math.random() * 100).toFixed(0);
    STATE.night_leds = [0, 0, 0, 0].map(() => Math.random() < 0.5 ? 1 : 0);
    STATE.night_mode = 'AUTO';
    STATE.buzzers.front = Math.random() < 0.05;
    STATE.buzzers.back = Math.random() < 0.05;
    // Update dashboard UI
    renderDashboard();
    updateStats();
}

// Patch: call setupSimulationToggle after login success too
const _orig_loginSuccess = loginSuccess;
loginSuccess = function () {
    _orig_loginSuccess();
    setupSimulationToggle();
};

const AUTH = {
    user: 'admin', // DEFAULT - CHANGE BEFORE PRODUCTION
    pass: 'admin123' // DEFAULT - CHANGE BEFORE PRODUCTION
};

function handleLogin(e) {
    e.preventDefault();
    const userIn = document.getElementById('username').value;
    const passIn = document.getElementById('password').value;
    const errorEl = document.getElementById('login-error');

    if (userIn === AUTH.user && passIn === AUTH.pass) {
        // Success
        sessionStorage.setItem('agro_auth_session', 'true');
        loginSuccess();
    } else {
        // Fail
        errorEl.innerText = "Invalid credentials";
    }
}

function loginSuccess() {
    toggleLoginScreen(false);
    initDashboard();
}

function logout() {
    sessionStorage.removeItem('agro_auth_session');
    if (updateInterval) clearInterval(updateInterval);
    toggleLoginScreen(true);
    window.location.reload();
}

function toggleLoginScreen(show) {
    const overlay = document.getElementById('login-overlay');
    const app = document.getElementById('app-container');

    if (show) {
        overlay.classList.remove('fade-out');
        app.classList.add('hidden');
    } else {
        overlay.classList.add('fade-out');
        setTimeout(() => {
            app.classList.remove('hidden');
        }, 500);
    }
}

function initDashboard() {
    applySettingsToUI();
    updatePirSectionVisibility();
    initStats();
    startDataPolling();
    setupSSE();
}


// UI Helper: Update Time
function updateTime() {
    const now = new Date();
    const el = document.getElementById('system-time');
    if (el) el.innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Heartbeat Logic
    updateSidebarStatus();
}

// Data Fetching Loop
let isOffline = false;
let lastConnectionAlertTime = 0;

let isWaitingForFirstConnection = true;

function startDataPolling() {
    if (updateInterval) clearInterval(updateInterval);
    updateInterval = setInterval(async () => {
        if (SIMULATION_MODE) return; // Skip fetching when in simulation mode

        try {
            const res = await fetch('/api/sensors');
            if (!res.ok) throw new Error("API Fail");
            const data = await res.json();
            Object.assign(STATE, data);

            // Real Online Check (Server time vs last hardware update)
            // last_update is from server.py (timestamp of last ESP32 packet)
            // If data.last_update is 0, we have never heard from ESP32.
            const nowSeconds = Date.now() / 1000;
            const hardwareDiff = nowSeconds - (data.last_update || 0);

            // STATE 1: NEVER CONNECTED (Waiting)
            if (!data.last_update || data.last_update === 0) {
                isWaitingForFirstConnection = true;
                isOffline = true; // Technically offline, but special case
                updateSidebarStatus();
            }

            // Debug: Show Tank Distance if available
            if (data.tankDist !== undefined && data.tankLevel < 5) {
                // Only log if low level to avoid spam, or finding the issue
                console.log(`Tank Debug: Dist ${data.tankDist}cm -> ${data.tankLevel}%`);
            }
            // STATE 2: CONNECTION LOST (Timeout > 10s)
            else if (hardwareDiff > 10) {
                isWaitingForFirstConnection = false; // We have connected at least once
                if (!isOffline) {
                    isOffline = true;
                    updateSidebarStatus();
                    addLog("Connection Lost - ESP32 Unreachable");
                }
                lastPacketTime = 0; // Force UI to show offline
            }
            // STATE 3: CONNECTED (Online < 10s)
            else {
                isWaitingForFirstConnection = false;
                lastPacketTime = Date.now(); // Used for UI animations
                if (isOffline) {
                    addLog("Reconnected to System");
                    showToast("System Online", "Data stream restored", "success");
                    isOffline = false;
                    updateSidebarStatus();
                }
            }

            // Alert every 10 seconds if offline AND NOT just waiting
            if (isOffline && !isWaitingForFirstConnection && Date.now() - lastConnectionAlertTime > 10000 && SETTINGS.notifications) {
                showToast("Connection Alert", "Cannot reach ESP32 Controller", "error");
                lastConnectionAlertTime = Date.now();
            }
        } catch (e) {
            // Network Failure (Server Unreachable)
            if (!isOffline) {
                isOffline = true;
                updateSidebarStatus();
                addLog("Connection Lost - Server Unreachable");
            }
        }

        // Alerts (Logic based on data values)
        if (SETTINGS.notifications && !isOffline) checkAlerts();

        renderDashboard();
        if (chartsInitialized) updateCharts();
        updateStats(); // Update stats widget
    }, 2000);
}

function updateSidebarStatus() {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    const syncEl = document.getElementById('last-sync');
    const headerStatus = document.getElementById('header-status'); // New Header Badge

    if (!indicator || !text) return;

    if (isOffline) {
        if (isWaitingForFirstConnection) {
            // CASE 1: WAITING FOR DEVICE
            text.innerText = "Waiting for Device...";
            text.style.color = "var(--text-muted)";

            indicator.style.background = "#f59e0b"; // Amber-500
            indicator.style.boxShadow = "none";
            indicator.classList.add('pulse-slow'); // Add CSS class for slow pulse if desired

            if (syncEl) syncEl.innerText = "Initializing...";

            // Header Badge
            if (headerStatus) {
                headerStatus.style.background = "rgba(245, 158, 11, 0.1)"; // Amber tint
                headerStatus.style.borderColor = "rgba(245, 158, 11, 0.2)";
                headerStatus.style.color = "#f59e0b";
                headerStatus.innerHTML = `<span class="spinner-small"></span><span style="font-weight:600; letter-spacing:0.5px;">SEARCHING...</span>`;
            }

        } else {
            // CASE 2: DISCONNECTED / ERROR
            text.innerText = "Offline";
            text.style.color = "var(--danger)";

            indicator.style.background = "var(--danger)";
            indicator.style.boxShadow = "none";
            indicator.classList.remove('pulse-slow');

            if (syncEl) syncEl.innerText = "Disconnected";

            // Header Badge
            if (headerStatus) {
                headerStatus.style.background = "rgba(225, 29, 72, 0.1)"; // Red tint
                headerStatus.style.borderColor = "rgba(225, 29, 72, 0.2)";
                headerStatus.style.color = "var(--danger)";
                headerStatus.innerHTML = `<span style="font-weight:600; letter-spacing:0.5px;">DISCONNECTED</span>`;
            }
        }

    } else {
        // CASE 3: ONLINE
        text.innerText = "Online";
        text.style.color = "var(--accent-emerald)";

        indicator.style.background = "var(--accent-emerald)";
        indicator.style.boxShadow = "0 0 10px var(--accent-emerald)";
        indicator.classList.remove('pulse-slow');

        if (syncEl) syncEl.innerText = "Just now";

        // Header Badge
        if (headerStatus) {
            headerStatus.style.background = "rgba(16,185,129,0.1)"; // Green tint
            headerStatus.style.borderColor = "rgba(16,185,129,0.2)";
            headerStatus.style.color = "var(--accent-emerald)";
            headerStatus.innerHTML = `<div class="pulse-status"></div><span style="font-weight:600; letter-spacing:0.5px;">ESP32 CONNECTED</span>`;
        }
    }
}


// Simulation Logic
// function simulateData removed

// Render UI
function renderDashboard() {
    // Env
    const tempEl = document.getElementById('temp-display');
    if (tempEl) {
        if (typeof STATE.temp === 'number') tempEl.innerText = STATE.temp.toFixed(1);
        else tempEl.innerText = STATE.temp;
    }

    const humEl = document.getElementById('hum-display');
    if (humEl) {
        if (typeof STATE.humidity === 'number') humEl.innerText = STATE.humidity.toFixed(1);
        else humEl.innerText = STATE.humidity;
    }

    const presEl = document.getElementById('pres-display');
    const badgeEl = document.getElementById('ai-prediction-badge');

    if (presEl) {
        if (typeof STATE.pressure === 'number') {
            presEl.innerText = STATE.pressure.toFixed(1);

            // AI Badge Logic - Enhanced with weather trend
            if (badgeEl) {
                const weatherTrend = STATE.ai_metrics?.weather_trend || 'stable';
                if (weatherTrend === 'storm_imminent' || STATE.pressure < 1000) {
                    badgeEl.innerText = "⛈️ STORM";
                    badgeEl.className = "badge-danger";
                } else if (weatherTrend === 'unsettled' || STATE.pressure < 1005) {
                    badgeEl.innerText = "☁️ UNSTABLE";
                    badgeEl.className = "badge-warning";
                } else if (STATE.pressure > 1020) {
                    badgeEl.innerText = "☀️ CLEAR";
                    badgeEl.className = "badge-neutral";
                } else {
                    badgeEl.innerText = "✓ STABLE";
                    badgeEl.className = "badge-neutral";
                }
            }
        }
        else presEl.innerText = STATE.pressure || "--";
    }

    // Update AI Status Indicator
    updateAIStatusIndicator();

    // Rain
    const rainEl = document.getElementById('rain-display');
    const rainCard = document.getElementById('card-rain');
    if (rainEl && rainCard) {
        if (STATE.rain) {
            rainEl.innerText = "Raining";
            rainCard.classList.add('raining');
        } else {
            rainEl.innerText = "Dry";
            rainCard.classList.remove('raining');
        }
    }

    const tankVal = document.getElementById('tank-val');
    const tankVis = document.getElementById('tank-level-visual');
    const tankDistEl = document.getElementById('tank-dist');

    if (tankVal) {
        if (typeof STATE.tankLevel === 'number') tankVal.innerText = Math.round(STATE.tankLevel);
        else tankVal.innerText = STATE.tankLevel;
    }
    if (tankVis) {
        if (typeof STATE.tankLevel === 'number') tankVis.style.height = `${STATE.tankLevel}%`;
        else tankVis.style.height = '0%';
    }
    if (tankDistEl) {
        if (STATE.tankDist >= 900) tankDistEl.innerText = "Err";
        else tankDistEl.innerText = STATE.tankDist;
    }
    updatePumpBtn('tank');

    updateSoilCard('div1', STATE.soil1);
    updateSoilCard('div2', STATE.soil2);
    updatePaddyCard(STATE.paddyLevel);

    // Update Average Soil Card
    let avgSoil = 0;
    let soilCount = 0;
    if (typeof STATE.soil1 === 'number') { avgSoil += STATE.soil1; soilCount++; }
    if (typeof STATE.soil2 === 'number') { avgSoil += STATE.soil2; soilCount++; }
    if (typeof STATE.soil3 === 'number') { avgSoil += STATE.soil3; soilCount++; }

    // Fallback if none are numbers (e.g. "--")
    let displayAvg = "--";
    if (soilCount > 0) {
        displayAvg = avgSoil / soilCount;
    }

    const avgValEl = document.getElementById('avg-soil-val');
    const avgBarEl = document.getElementById('avg-soil-bar');

    if (avgValEl) {
        if (typeof displayAvg === 'number') avgValEl.innerText = Math.round(displayAvg);
        else avgValEl.innerText = displayAvg;
    }
    if (avgBarEl) {
        if (typeof displayAvg === 'number') avgBarEl.style.width = `${displayAvg}%`;
        else avgBarEl.style.width = '0%';
    }

    // Security - Update PIR status display
    updateSecurityCard('front', STATE.pir1);
    // Update Buzzer/Lockdown button state
    updateBuzzerBtn('front');

    // Light & Night System
    const ldrDisplay = document.getElementById('ldr-display');
    const ldrStatus = document.getElementById('ldr-status');

    if (ldrDisplay && ldrStatus) {
        ldrDisplay.innerText = STATE.ldr;
        // Simple logic for status text
        if (STATE.ldr > 2000) ldrStatus.innerText = "Dark (Night Mode)";
        else ldrStatus.innerText = "Light (Day Mode)";
    }

    // LEDs
    if (STATE.night_leds && Array.isArray(STATE.night_leds)) {
        for (let i = 0; i < 4; i++) {
            const el = document.getElementById(`led-indicator-${i + 1}`);
            if (el) {
                if (STATE.night_leds[i]) el.classList.add('active');
                else el.classList.remove('active');
            }
        }
    }

    // Night Mode Buttons
    ['AUTO', 'ON', 'OFF'].forEach(mode => {
        const btn = document.getElementById(`btn-night-${mode.toLowerCase()}`);
        if (btn) {
            if (STATE.night_mode === mode) btn.classList.add('btn-active');
            else btn.classList.remove('btn-active');
        }
    });

}

// Update AI Status Indicator in header
function updateAIStatusIndicator() {
    const aiStatus = document.getElementById('ai-status-indicator');
    if (!aiStatus) return;

    const aiMetrics = STATE.ai_metrics || {};
    const etFactor = aiMetrics.evaporation_factor || 0;
    const stressIndex = aiMetrics.crop_stress_index || 0;
    const confidence = STATE.ai_status?.confidence || 0;

    // Update the AI status display
    let statusText = 'AI ACTIVE';
    let statusColor = 'rgba(139, 92, 246, 0.1)';
    let borderColor = 'rgba(139, 92, 246, 0.2)';
    let textColor = 'var(--accent-indigo)';

    if (stressIndex > 50) {
        statusText = `AI: STRESS ${stressIndex.toFixed(0)}%`;
        statusColor = 'rgba(225, 29, 72, 0.1)';
        borderColor = 'rgba(225, 29, 72, 0.2)';
        textColor = 'var(--danger)';
    } else if (etFactor > 0.6) {
        statusText = `AI: HIGH ET ${(etFactor * 100).toFixed(0)}%`;
        statusColor = 'rgba(245, 158, 11, 0.1)';
        borderColor = 'rgba(245, 158, 11, 0.2)';
        textColor = 'var(--warning)';
    } else if (confidence > 0) {
        statusText = `AI ACTIVE (${confidence}%)`;
    }

    aiStatus.style.background = statusColor;
    aiStatus.style.borderColor = borderColor;
    aiStatus.style.color = textColor;
    aiStatus.innerHTML = `<div class="pulse-purple"></div><span style="font-weight:600; letter-spacing:0.5px;">${statusText}</span>`;
}

async function setNightMode(mode) {
    // Optimistic Update
    STATE.night_mode = mode;
    renderDashboard();

    try {
        await fetch(`/api/control?night=${mode}&state=1`, { method: 'POST' });
        addLog(`Night Mode set to ${mode}`);
    } catch (e) {
        console.error("Control failed", e);
    }
}

function renderSecurity() {
    updateSecurityCard('front', STATE.pir1);
    //updateSecurityCard('back', STATE.pir2);
    updateBuzzerBtn('front');
    //updateBuzzerBtn('back');
}

function updateSecurityCard(zone, isMotion) {
    const card = document.getElementById(`card-sec-${zone}`);
    const vis = document.getElementById(`vis-${zone}`);
    const statusText = document.getElementById(`pir${zone === 'front' ? '1' : '2'}-status`);

    if (!card || !vis) return;

    if (isMotion) {
        // BREACH MODE
        card.classList.add('breach');
        vis.classList.remove('secure');
        vis.classList.add('danger');
        vis.innerHTML = `<svg width="32" height="32" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>`;
        statusText.innerText = "⚠️ BREACH DETECTED";
        statusText.style.color = "var(--danger)";
    } else {
        // SECURE MODE
        card.classList.remove('breach');
        vis.classList.remove('danger');
        vis.classList.add('secure');
        vis.innerHTML = `<svg width="32" height="32" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`;
        statusText.innerText = "SECURE MONITORING";
        statusText.style.color = "var(--accent-emerald)";
    }
}

function updateBuzzerBtn(zone) {
    const btn = document.getElementById(`btn-buzzer-${zone}`);
    if (!btn) return;

    const isOn = STATE.buzzers && STATE.buzzers[zone];

    if (isOn) {
        btn.classList.add('active');
        btn.innerText = "⛔ DEACTIVATE ALARM";
    } else {
        btn.classList.remove('active');
        btn.innerText = "ACTIVATE LOCKDOWN";
    }
}


function updatePaddyCard(value) {
    const valEl = document.getElementById('paddy-val');
    const barEl = document.getElementById('paddy-bar');

    if (valEl) {
        if (typeof value === 'number') valEl.innerText = Math.round(value);
        else valEl.innerText = value;
    }
    if (barEl) {
        if (typeof value === 'number') barEl.style.width = `${value}%`;
        else barEl.style.width = '0%';
    }
    updatePumpBtn('div3');
}

function updateSoilCard(id, value) {
    const valEl = document.getElementById(`soil${id.replace('div', '')}-val`);
    const barEl = document.getElementById(`soil${id.replace('div', '')}-bar`);

    if (valEl) {
        if (typeof value === 'number') valEl.innerText = Math.round(value);
        else valEl.innerText = value;
    }
    if (barEl) {
        if (typeof value === 'number') barEl.style.width = `${value}%`;
        else barEl.style.width = '0%';
    }

    const card = document.getElementById(`card-${id}`);
    if (card && typeof value === 'number') {
        if (value < SETTINGS.dryThreshold) card.setAttribute('data-status', 'dry');
        else if (value < SETTINGS.wetThreshold) card.setAttribute('data-status', 'moist');
        else card.setAttribute('data-status', 'wet');
    }

    updatePumpBtn(id);
}

function updatePumpBtn(id) {
    // New Logic: 3-Button Group (handled in DOM update usually, but let's assume we replace the element)
    // We will target the btn-group container.

    // We assume HTML has been updated to have btn-group-$id
    ['AUTO', 'ON', 'OFF'].forEach(mode => {
        const btn = document.getElementById(`btn-${id}-${mode.toLowerCase()}`);
        if (btn) {
            const currentMode = STATE.pump_modes ? STATE.pump_modes[id] : 'AUTO';
            if (currentMode === mode) btn.classList.add('btn-active');
            else btn.classList.remove('btn-active');
        }
    });

    // Also update the status indicator (Spinning Icon or Text)
    // Using existing 'btn-$id' as a fallback if not using groups? No, we will change HTML.
}

// Controls
// Controls
async function setPumpMode(id, mode) {
    // Optimistic Update
    if (!STATE.pump_modes) STATE.pump_modes = {};
    STATE.pump_modes[id] = mode;
    renderDashboard();

    try {
        await fetch(`/api/control?pump=${id}&state=${mode}`, { method: 'POST' });
        addLog(`Set ${id.toUpperCase()} to ${mode}`);
    } catch (e) {
        console.error("Control failed", e);
    }
}

// Security Controls
async function toggleBuzzer(id) {
    const currentState = STATE.buzzers[id];
    const newState = !currentState;
    STATE.buzzers[id] = newState;
    renderDashboard();

    try {
        await fetch(`/api/control?buzzer=${id}&state=${newState ? 1 : 0}`, { method: 'POST' });
        addLog(`Manual ${newState ? 'Lockdown' : 'Unlock'} for ${id.toUpperCase()}`);
    } catch (e) {
        console.error("Control failed", e);
        STATE.buzzers[id] = currentState;
        renderDashboard();
    }
}

// Logs 
function addLog(msg) {
    const feed = document.getElementById('ai-feed');
    if (!feed) return;

    const el = document.createElement('div');
    // Glassmorphism styling for logs
    el.style.background = "rgba(255, 255, 255, 0.03)";
    el.style.padding = "0.75rem 1rem";
    el.style.borderRadius = "8px";
    el.style.marginBottom = "0.5rem";
    el.style.fontSize = "0.85rem";
    el.style.color = "var(--text-main)";
    el.style.fontFamily = "var(--font-mono)";
    el.style.display = "flex";
    el.style.gap = "0.5rem"; // Gap for flex items

    // Icon Logic
    let icon = "📝";
    let color = "var(--accent-emerald)";

    if (msg.startsWith("AI Action:")) {
        icon = "⚡";
        color = "var(--accent-emerald)";
        msg = msg.replace("AI Action:", "").trim();
    }
    else if (msg.startsWith("AI:")) {
        icon = "🤖";
        color = "var(--accent-purple)";
    }
    else if (msg.startsWith("DEVICE:")) {
        icon = "📡";
        color = "var(--accent-cyan)";
        msg = msg.replace("DEVICE:", "").trim();
    }
    else if (msg.startsWith("Manual")) {
        icon = "🕹️";
        color = "var(--danger)";
    }

    el.style.borderLeft = `3px solid ${color}`;

    // Add time and message
    el.innerHTML = `<span style="color:var(--text-muted)">[${new Date().toLocaleTimeString()}]</span> <span>${icon} ${msg}</span>`;

    feed.prepend(el);
    if (feed.children.length > 50) feed.lastChild.remove();
}

// Mode Toggle
// function toggleMockMode removed

// SSE
function setupSSE() {
    const evtSource = new EventSource("/events");

    evtSource.addEventListener("ai_decision", (e) => {
        addLog(`AI: ${e.data}`);

        // Visual Feedback
        const aiStatus = document.getElementById('ai-status-indicator');
        if (aiStatus) {
            aiStatus.style.background = "rgba(139, 92, 246, 0.3)";
            setTimeout(() => {
                aiStatus.style.background = "rgba(139, 92, 246, 0.1)";
            }, 500);
        }
    });

    evtSource.addEventListener("sys_log", (e) => {
        addLog(e.data); // e.g. "DEVICE: Motion Detected"
    });

    evtSource.onerror = () => {
        console.log("SSE disconnected");
    };
}


/* --- Analytics & Navigation Logic --- */
function switchTab(tabName) {
    const dashboardView = document.getElementById('view-dashboard');
    const analyticsView = document.getElementById('view-analytics');
    const settingsView = document.getElementById('view-settings');



    try {
        console.log("Switching to", tabName);
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

        // Navbar Logic
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            const onClickAttr = item.getAttribute('onclick');
            if (onClickAttr && onClickAttr.includes(tabName)) {
                item.classList.add('active');
            }
        });

        // Hide All (Resetting Classes)
        if (dashboardView) {
            dashboardView.classList.add('hidden');
            dashboardView.style.display = ''; // Clear inline override
        }
        if (analyticsView) {
            analyticsView.classList.add('hidden');
            analyticsView.style.display = '';
        }
        if (settingsView) {
            settingsView.classList.add('hidden');
            settingsView.style.display = '';
        }

        // Show Specific
        if (tabName === 'dashboard' && dashboardView) {
            dashboardView.classList.remove('hidden');
        } else if (tabName === 'analytics' && analyticsView) {
            analyticsView.classList.remove('hidden');

            if (!chartsInitialized) {
                initCharts();
                chartsInitialized = true;
            }
        } else if (tabName === 'settings' && settingsView) {
            settingsView.classList.remove('hidden');
        }
    } catch (e) {
        console.error("Tab Switch Error:", e);
    }
}

/* --- Analytics Logic --- */



function saveSettings() {
    SETTINGS.username = document.getElementById('setting-username').value;
    SETTINGS.notifications = document.getElementById('setting-notif').checked;
    SETTINGS.dryThreshold = parseInt(document.getElementById('setting-dry').value);
    SETTINGS.wetThreshold = parseInt(document.getElementById('setting-wet').value);
    SETTINGS.wetThreshold = parseInt(document.getElementById('setting-wet').value);
    SETTINGS.pirSensorEnabled = document.getElementById('setting-pir').checked;

    sessionStorage.setItem('agro_settings', JSON.stringify(SETTINGS));
    applySettingsToUI();
    updatePirSectionVisibility();
    alert("Settings Saved!");

    // Update greeting immediately if changed
    const greetEl = document.getElementById('greeting');
    if (greetEl) greetEl.innerText = `Welcome Back, ${SETTINGS.username}`;
}

function loadSettings() {
    const stored = sessionStorage.getItem('agro_settings');
    if (stored) {
        const parsed = JSON.parse(stored);
        Object.assign(SETTINGS, parsed);
    }
    applySettingsToUI();
}

/* --- Live Alerts Logic --- */
let lastAlertTime = {
    pir: 0,
    soil: 0,
    temp: 0
};

function showToast(title, msg, type = 'alert-success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const el = document.createElement('div');
    el.className = `toast-card ${type}`;

    // Icon
    let icon = "ℹ️";
    if (type.includes('danger')) icon = "🚨";
    if (type.includes('warning')) icon = "⚠️";
    if (type.includes('success')) icon = "✅";

    el.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">
                <span class="toast-title">${title}</span>
                <span class="toast-msg">${msg}</span>
            </div>
        `;

    container.appendChild(el);

    // Remove after 4s
    setTimeout(() => {
        el.style.animation = "fadeOut 0.5s ease forwards";
        setTimeout(() => el.remove(), 500);
    }, 4000);
}

// Track previous PIR state for edge detection in dashboard
let lastPirState = false;

function checkAlerts() {
    const now = Date.now();

    // 1. Security Alert - PIR Motion Detection (Throttle: 10s for toast)
    if (STATE.pir1 && (now - lastAlertTime.pir > 10000)) {
        showToast("🚨 Security Alert", "Motion detected in perimeter zone!", "alert-danger");
        updateSecurityCard('front', true);
        lastAlertTime.pir = now;
    } else if (!STATE.pir1) {
        updateSecurityCard('front', false);
    }

    // Play beep ONCE when motion is first detected (edge detection)
    if (STATE.pir1 && !lastPirState) {
        playMotionAlert(); // Single beep for motion
    }
    lastPirState = STATE.pir1;

    // 2. Soil Moisture (Throttle: 60s)
    if ((STATE.soil2 < SETTINGS.dryThreshold) && (now - lastAlertTime.soil > 60000)) {
        showToast("Irrigation Alert", "Soil moisture below critical threshold", "alert-warning");
        lastAlertTime.soil = now;
    }

    // 3. Temperature (Throttle: 60s)
    if (STATE.temp > 35 && (now - lastAlertTime.temp > 60000)) {
        showToast("High Temperature", `Current temp is ${STATE.temp.toFixed(1)}°C`, "alert-warning");
        lastAlertTime.temp = now;
    }
}

function applySettingsToUI() {
    const userEl = document.getElementById('setting-username');
    if (userEl) userEl.value = SETTINGS.username;

    const notifEl = document.getElementById('setting-notif');
    if (notifEl) notifEl.checked = SETTINGS.notifications;

    const dryEl = document.getElementById('setting-dry');
    if (dryEl) dryEl.value = SETTINGS.dryThreshold;

    const wetEl = document.getElementById('setting-wet');
    if (wetEl) wetEl.value = SETTINGS.wetThreshold;

    const pirEl = document.getElementById('setting-pir');
    if (pirEl) pirEl.checked = SETTINGS.pirSensorEnabled;

    const greetEl = document.getElementById('greeting');
}

function updatePirSectionVisibility() {
    const securitySection = document.getElementById('card-security');
    if (securitySection) {
        securitySection.style.display = SETTINGS.pirSensorEnabled ? 'grid' : 'none';
    }
}


async function initCharts() {
    try {
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
        Chart.defaults.font.family = "'Outfit', sans-serif";
        Chart.defaults.color = '#64748b'; // Slate-500
        Chart.defaults.borderColor = '#e2e8f0'; // Slate-200

        // Fetch History OR Generate Fallback (Offline Mode)
        let historyData = [];
        try {
            const res = await fetch('/api/history');
            if (res.ok) historyData = await res.json();
        } catch (e) { console.warn("History Fetch Failed - Using Placeholder"); }

        if (historyData.length === 0) {
            // Generate Dummy Data for Visuals if Offline
            const now = new Date();
            for (let i = 20; i > 0; i--) {
                const t = new Date(now.getTime() - i * 3600000); // Past hours
                historyData.push({
                    time: t.getHours() + ":00",
                    temp: 20 + Math.random() * 10,
                    humidity: 50 + Math.random() * 20,
                    avg_soil: 40 + Math.random() * 40
                });
            }
        }

        const labels = historyData.map(d => d.time);
        const temps = historyData.map(d => d.temp);
        const hums = historyData.map(d => d.humidity);
        const soils = historyData.map(d => d.avg_soil || 0);

        // 1. Env Chart (Line Area)
        const ctxEnv = document.getElementById('chart-env').getContext('2d');
        const gradTemp = ctxEnv.createLinearGradient(0, 0, 0, 300);
        gradTemp.addColorStop(0, 'rgba(245, 158, 11, 0.4)');
        gradTemp.addColorStop(1, 'rgba(245, 158, 11, 0)');

        const gradHum = ctxEnv.createLinearGradient(0, 0, 0, 300);
        gradHum.addColorStop(0, 'rgba(6, 182, 212, 0.4)');
        gradHum.addColorStop(1, 'rgba(6, 182, 212, 0)');

        chartInstances.env = new Chart(ctxEnv, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Temperature (°C)',
                        data: temps,
                        borderColor: '#f59e0b', // Amber
                        backgroundColor: gradTemp,
                        tension: 0.4,
                        fill: true,
                        pointRadius: 2,
                    },
                    {
                        label: 'Humidity (%)',
                        data: hums,
                        borderColor: '#06b6d4', // Cyan
                        backgroundColor: gradHum,
                        tension: 0.4,
                        fill: true,
                        pointRadius: 2,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top', align: 'end' } },
                scales: {
                    x: { grid: { display: false } },
                    y: { border: { display: false }, grid: { borderDash: [5, 5] } }
                },
                interaction: { mode: 'index', intersect: false }
            }
        });

        // 2. Soil Moisture (Bar)
        const ctxSoil = document.getElementById('chart-soil').getContext('2d');
        chartInstances.soil = new Chart(ctxSoil, {
            type: 'bar',
            data: {
                labels: ['Zone Alpha', 'Zone Beta', 'Zone Gamma'],
                datasets: [{
                    label: 'Moisture Level (%)',
                    data: [STATE.soil1 || 45, STATE.soil2 || 60, STATE.soil3 || 30],
                    backgroundColor: ['#10b981', '#0ea5e9', '#6366f1'],
                    borderRadius: 6,
                    barThickness: 50
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, max: 100, grid: { borderDash: [5, 5] } },
                    x: { grid: { display: false } }
                }
            }
        });

        // 3. Radar Chart (System Balance)
        const ctxRadar = document.getElementById('chart-radar').getContext('2d');
        if (ctxRadar) {
            chartInstances.radar = new Chart(ctxRadar, {
                type: 'radar',
                data: {
                    labels: ['Temperature', 'Humidity', 'Soil A', 'Soil B', 'Soil C', 'Tank Level'],
                    datasets: [{
                        label: 'System Metrics',
                        data: [65, 59, 90, 81, 56, 40], // Placeholder defaults
                        fill: true,
                        backgroundColor: 'rgba(99, 102, 241, 0.2)',
                        borderColor: '#6366f1',
                        pointBackgroundColor: '#6366f1',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: '#6366f1'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    elements: { line: { borderWidth: 3 } },
                    scales: { r: { angleLines: { display: false }, suggestedMin: 0, suggestedMax: 100 } }
                }
            });
        }

        // 4. Doughnut Chart (Power/Resource Distribution)
        const ctxDoughnut = document.getElementById('chart-doughnut').getContext('2d');
        if (ctxDoughnut) {
            chartInstances.doughnut = new Chart(ctxDoughnut, {
                type: 'doughnut',
                data: {
                    labels: ['Irrigation', 'Sensors', 'Idle', 'Processing'],
                    datasets: [{
                        label: 'Resource Usage',
                        data: [30, 15, 45, 10],
                        backgroundColor: ['#3b82f6', '#10b981', '#e2e8f0', '#f59e0b'],
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: { legend: { position: 'right' } }
                }
            });
        }

    } catch (e) {
        console.error("Chart Init Fail", e);
    }
}

function updateCharts() {
    if (!chartInstances.soil) return;

    // Update Soil
    chartInstances.soil.data.datasets[0].data = [STATE.soil1, STATE.soil2, STATE.soil3];
    chartInstances.soil.update('none'); // No animation for performance

    // Update Env (Add new point if needed, usually we re-fetch history or just append state)
    // For now, let's just push live endpoint to chart to make it look "alive"
    if (chartInstances.env) {
        const now = new Date().toLocaleTimeString();
        if (chartInstances.env.data.labels.length > 20) {
            chartInstances.env.data.labels.shift();
            chartInstances.env.data.datasets[0].data.shift();
            chartInstances.env.data.datasets[1].data.shift();
        }
        chartInstances.env.data.labels.push(now);
        chartInstances.env.data.datasets[0].data.push(STATE.temp);
        chartInstances.env.data.datasets[1].data.push(STATE.humidity);
        chartInstances.env.data.update('none');
    }
}
