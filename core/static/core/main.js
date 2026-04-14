/*
    main.js — Rewright UI Controller

    1. Solar system background
    2. Theme toggling
    3. Character counters (both panels)
    4. Rewrite button → API call
    5. Result + inline stats + collapsible changes
    6. Copy with checkmark
    7. Toast
*/


/* ═══════════════════════════════════════════════════════════════════
   1. SOLAR SYSTEM BACKGROUND
   ═══════════════════════════════════════════════════════════════════ */

const canvas = document.getElementById('solar-system');
const ctx = canvas.getContext('2d');
let isPremium = false;
let time = 0;

const sun = { xRatio: 0.15, yRatio: 0.35 };

const planets = [
    { orbitA: 0.08,  orbitB: 0.05, speed: 0.008,  size: 2.5, offset: 0,   color: [140,140,140] },  // Mercury — gray
    { orbitA: 0.14,  orbitB: 0.08, speed: 0.005,  size: 4,   offset: 1.2, color: [232,205,160] },  // Venus — pale yellow
    { orbitA: 0.22,  orbitB: 0.12, speed: 0.003,  size: 4.5, offset: 2.8, color: [75,125,201] },   // Earth — blue
    { orbitA: 0.32,  orbitB: 0.17, speed: 0.002,  size: 3.5, offset: 0.7, color: [193,68,14] },    // Mars — red-orange
    { orbitA: 0.42,  orbitB: 0.22, speed: 0.0012, size: 7,   offset: 4.1, color: [200,139,58] },   // Jupiter — orange-brown
    { orbitA: 0.55,  orbitB: 0.28, speed: 0.0008, size: 6,   offset: 3.0, color: [228,209,145] },  // Saturn — golden
];

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

function drawSolarSystem() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const sunX = canvas.width * sun.xRatio;
    const sunY = canvas.height * sun.yRatio;
    const alpha = isPremium ? 1 : 0.4;
    const glowSize = isPremium ? 40 : 20;
    const sunPulse = 1 + Math.sin(time * 0.02) * 0.15;

    /* Sun glow */
    const grad = ctx.createRadialGradient(sunX, sunY, 0, sunX, sunY, glowSize * sunPulse);
    if (isPremium) {
        grad.addColorStop(0, 'rgba(240,160,48,0.6)');
        grad.addColorStop(0.3, 'rgba(240,160,48,0.15)');
        grad.addColorStop(1, 'rgba(240,160,48,0)');
    } else {
        grad.addColorStop(0, 'rgba(194,102,10,0.25)');
        grad.addColorStop(0.3, 'rgba(194,102,10,0.06)');
        grad.addColorStop(1, 'rgba(194,102,10,0)');
    }
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(sunX, sunY, glowSize * sunPulse, 0, Math.PI * 2);
    ctx.fill();

    /* Sun core */
    ctx.beginPath();
    ctx.arc(sunX, sunY, isPremium ? 5 : 3, 0, Math.PI * 2);
    ctx.fillStyle = isPremium ? 'rgba(240,160,48,0.8)' : 'rgba(194,102,10,0.35)';
    ctx.fill();

    /* Orbits + planets */
    for (const p of planets) {
        const a = p.orbitA * canvas.width;
        const b = p.orbitB * canvas.height;
        const angle = p.offset + time * p.speed;

        /* Orbit ring */
        ctx.beginPath();
        ctx.ellipse(sunX, sunY, a, b, 0, 0, Math.PI * 2);
        ctx.strokeStyle = isPremium
            ? 'rgba(240,160,48,0.06)'
            : 'rgba(194,102,10,0.04)';
        ctx.lineWidth = 1;
        ctx.stroke();

        /* Planet position */
        const px = sunX + Math.cos(angle) * a;
        const py = sunY + Math.sin(angle) * b;

        /* Planet glow (premium) */
        if (isPremium) {
            const pg = ctx.createRadialGradient(px, py, 0, px, py, p.size * 3);
            pg.addColorStop(0, `rgba(${p.color[0]},${p.color[1]},${p.color[2]},0.2)`);
            pg.addColorStop(1, `rgba(${p.color[0]},${p.color[1]},${p.color[2]},0)`);
            ctx.fillStyle = pg;
            ctx.beginPath();
            ctx.arc(px, py, p.size * 3, 0, Math.PI * 2);
            ctx.fill();
        }

        /* Planet body */
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color[0]},${p.color[1]},${p.color[2]},${alpha * 0.5})`;
        ctx.fill();
    }

    time++;
    requestAnimationFrame(drawSolarSystem);
}

resizeCanvas();
drawSolarSystem();
window.addEventListener('resize', resizeCanvas);


/* ═══════════════════════════════════════════════════════════════════
   2. DOM REFERENCES
   ═══════════════════════════════════════════════════════════════════ */

const inputText   = document.getElementById('input-text');
const outputArea  = document.getElementById('output-area');
const inputMeta   = document.getElementById('input-meta');
const outputMeta  = document.getElementById('output-meta');
const btnRewrite  = document.getElementById('btn-rewrite');
const btnCopy     = document.getElementById('btn-copy');
const toast       = document.getElementById('toast');
const toggleDeep  = document.getElementById('toggle-deep');
const modeQuick   = document.getElementById('mode-quick');
const modeDeep    = document.getElementById('mode-deep');
const resultStats = document.getElementById('result-stats');
/* Voice calibration elements */
const voiceSection = document.getElementById('voice-section');
const voiceToggle  = document.getElementById('voice-toggle');
const voiceBody    = document.getElementById('voice-body');
const voiceSample  = document.getElementById('voice-sample');
const voiceCount   = document.getElementById('voice-count');

const VOICE_MIN_WORDS = 200;
const VOICE_MIN_CHARS = 1000;
document.querySelector('.btn-text').textContent = 'Quick Fix';


/* ═══════════════════════════════════════════════════════════════════
   3. CHARACTER COUNTERS — both panels
   ═══════════════════════════════════════════════════════════════════ */

inputText.addEventListener('input', function () {
    const len = this.value.length;
    const words = this.value.trim() ? this.value.trim().split(/\s+/).length : 0;
    inputMeta.textContent = words > 0 ? `${words.toLocaleString()} words · ${len.toLocaleString()} chars` : '0';
    btnRewrite.disabled = len === 0;
});

/**
 * Update the output character/word count.
 * Called after result is displayed.
 */
function updateOutputMeta(text) {
    const len = text.length;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    outputMeta.textContent = `${words.toLocaleString()} words · ${len.toLocaleString()} chars`;
}


/* ═══════════════════════════════════════════════════════════════════
   4. TOGGLE
   ═══════════════════════════════════════════════════════════════════ */

toggleDeep.addEventListener('change', function () {
    if (this.checked) {
        isPremium = true;
        document.body.classList.add('premium');
        modeQuick.classList.remove('active');
        modeDeep.classList.add('active');
        document.querySelector('.btn-text').textContent = 'Deep Rewrite';
    } else {
        isPremium = false;
        document.body.classList.remove('premium');
        modeQuick.classList.add('active');
        modeDeep.classList.remove('active');
        document.querySelector('.btn-text').textContent = 'Quick Fix';
    }

    /*
     * If there's already a result, pulse the button to hint
     * "press me again to rewrite with the new mode"
     */
    const hasResult = document.getElementById('output-text');
    if (hasResult && !btnRewrite.disabled) {
        btnRewrite.classList.add('pulse');
        setTimeout(() => btnRewrite.classList.remove('pulse'), 800);
    }
});

modeQuick.addEventListener('click', function () {
    if (toggleDeep.checked) {
        toggleDeep.checked = false;
        toggleDeep.dispatchEvent(new Event('change'));
    }
});

modeDeep.addEventListener('click', function () {
    if (!toggleDeep.checked) {
        toggleDeep.checked = true;
        toggleDeep.dispatchEvent(new Event('change'));
    }
});

/* ═══════════════════════════════════════════════════════════════════
   VOICE CALIBRATION
   ═══════════════════════════════════════════════════════════════════ */

/* Toggle open/close */
voiceToggle.addEventListener('click', function () {
    voiceSection.classList.toggle('open');
});

/* Update word/char count as user types */
voiceSample.addEventListener('input', function () {
    const text = this.value;
    const len = text.length;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;

    voiceCount.textContent = `${words.toLocaleString()} words · ${len.toLocaleString()} chars`;

    /* Show green when minimum is met */
    if (words >= VOICE_MIN_WORDS && len >= VOICE_MIN_CHARS) {
        voiceCount.classList.add('valid');
    } else {
        voiceCount.classList.remove('valid');
    }
});

/**
 * Check if voice sample is valid.
 * Returns the sample text if valid, empty string if no sample,
 * or null if sample exists but is too short (shows error).
 */
function getVoiceSample() {
    const text = voiceSample.value.trim();

    /* No sample at all — that's fine, it's optional */
    if (text.length === 0) return '';

    const words = text.split(/\s+/).length;
    const chars = text.length;

    /* Sample exists but too short */
    if (words < VOICE_MIN_WORDS || chars < VOICE_MIN_CHARS) {
        return null;
    }

    return text;
}


/* ═══════════════════════════════════════════════════════════════════
   5. REWRITE BUTTON
   ═══════════════════════════════════════════════════════════════════ */

btnRewrite.addEventListener('click', async function () {
    const text = inputText.value.trim();
    if (!text) return;

    showLoading();

    try {
        const result = await callAPI(text);
        showResult(result);
    } catch (error) {
        console.error('Rewrite failed:', error);
        showError(error.message);
    }
});


/* ═══════════════════════════════════════════════════════════════════
   6. API CALL
   ═══════════════════════════════════════════════════════════════════ */

async function callAPI(text) {
    const deepRewrite = toggleDeep.checked;
    const voiceSampleText = getVoiceSample();

    /* Voice sample exists but too short */
    if (voiceSampleText === null) {
        const words = voiceSample.value.trim().split(/\s+/).length;
        const chars = voiceSample.value.trim().length;
        throw new Error(
            `Voice sample too short: ${words} words / ${chars} chars. ` +
            `Need at least ${VOICE_MIN_WORDS} words and ${VOICE_MIN_CHARS} chars. ` +
            `Add more text or clear the sample to use default style.`
        );
    }

    const response = await fetch('/api/humanize/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text,
            deep_rewrite: deepRewrite,
            voice_sample: voiceSampleText,
        }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Something went wrong');
    return data;
}


/* ═══════════════════════════════════════════════════════════════════
   7. UI STATES
   ═══════════════════════════════════════════════════════════════════ */

function showLoading() {
    btnRewrite.disabled = true;
    document.querySelector('.btn-text').textContent = 'Rewriting...';
    btnCopy.style.display = 'none';
    outputMeta.textContent = '';
    resultStats.style.display = 'none';

    /* Remove previous changes report */
    const existing = document.querySelector('.changes-report');
    if (existing) existing.remove();

    const message = toggleDeep.checked
        ? 'Deep rewriting with AI...'
        : 'Applying pattern fixes...';

    outputArea.innerHTML = `
        <div class="loading-state">
            <div class="orbital-spinner">
                <div class="ring"></div>
                <div class="ring"></div>
                <div class="ring"></div>
                <div class="core"></div>
            </div>
            <p>${message}</p>
            <div class="loading-bar">
                <div class="loading-bar-fill"></div>
            </div>
        </div>
    `;
}

function showResult(result) {
    btnRewrite.disabled = false;
    document.querySelector('.btn-text').textContent = toggleDeep.checked ? 'Deep Rewrite' : 'Quick Fix';

    /* Output text */
    outputArea.innerHTML = `<div id="output-text">${escapeHtml(result.text)}</div>`;

    if (result.warning) {
        outputArea.innerHTML += `<div class="warning-bar">${escapeHtml(result.warning)}</div>`;
    }

    /* Update output word count */
    updateOutputMeta(result.text);

    /* Show inline stats */
    const origWords = result.stats.original_words;
    const finalWords = result.stats.final_words;
    const patternsFound = result.stats.patterns_found;

    resultStats.innerHTML = `
        <span>${origWords}</span> → <span>${finalWords}</span> words
        <span class="stat-dot">·</span>
        <span>${patternsFound}</span> patterns
    `;
    resultStats.style.display = 'block';

    /* Collapsible changes report */
    if (result.changes && result.changes.length > 0) {
        const reportEl = buildChangesReport(result.changes);
        const panelOutput = document.getElementById('panel-output');
        panelOutput.appendChild(reportEl);
    }

    btnCopy.style.display = 'flex';
}

function showError(message) {
    btnRewrite.disabled = false;
    document.querySelector('.btn-text').textContent = toggleDeep.checked ? 'Deep Rewrite' : 'Quick Fix';
    resultStats.style.display = 'none';

    outputArea.innerHTML = `
        <div class="output-placeholder" style="color: #dc2626;">
            <div class="placeholder-orb">
                <span style="background:#dc2626;"></span>
                <span style="background:#dc2626;"></span>
                <span style="background:#dc2626;"></span>
            </div>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
}


/* ═══════════════════════════════════════════════════════════════════
   8. CHANGES REPORT — COLLAPSIBLE
   ═══════════════════════════════════════════════════════════════════ */

function buildChangesReport(changes) {
    const existing = document.querySelector('.changes-report');
    if (existing) existing.remove();

    const wrapper = document.createElement('div');
    wrapper.className = 'changes-report';

    let items = '';
    for (const change of changes) {
        items += `
            <div class="change-item">
                <span class="change-badge">P${change.pattern}</span>
                <div class="change-content">
                    <strong>${escapeHtml(change.name)}</strong>
                    <span class="change-detail">${escapeHtml(change.detail)}</span>
                </div>
            </div>
        `;
    }

    wrapper.innerHTML = `
        <div class="changes-toggle">
            <span class="changes-toggle-text">${changes.length} patterns detected</span>
            <span class="changes-toggle-arrow">▾</span>
        </div>
        <div class="changes-list">${items}</div>
    `;

    wrapper.querySelector('.changes-toggle').addEventListener('click', function () {
        wrapper.classList.toggle('open');
    });

    return wrapper;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}


/* ═══════════════════════════════════════════════════════════════════
   9. COPY — ICON SWAP TO CHECKMARK
   ═══════════════════════════════════════════════════════════════════ */

const ICON_COPY = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
</svg>`;

const ICON_CHECK = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="20 6 9 17 4 12"/>
</svg>`;

btnCopy.addEventListener('click', async function () {
    const outputText = document.getElementById('output-text');
    if (!outputText) return;

    try {
        await navigator.clipboard.writeText(outputText.textContent);

        btnCopy.innerHTML = ICON_CHECK;
        btnCopy.classList.add('copied');

        setTimeout(() => {
            btnCopy.innerHTML = ICON_COPY;
            btnCopy.classList.remove('copied');
        }, 1500);

        showToast('Copied to clipboard');
    } catch (error) {
        showToast('Could not copy — select manually');
    }
});


/* ═══════════════════════════════════════════════════════════════════
   10. TOAST
   ═══════════════════════════════════════════════════════════════════ */

function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
}