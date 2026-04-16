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

/*
    SOLAR SYSTEM — Realistic 3D planets with accurate size ratios

    Real planet size ratios (Earth = 1.0):
        Mercury: 0.38    Venus: 0.95     Earth: 1.0      Mars: 0.53
        Jupiter: 11.2    Saturn: 9.45    Uranus: 4.0     Neptune: 3.88
        Sun: 109.2

    We use square-root compression so Jupiter/Saturn don't dominate
    the screen while still looking proportionally correct.

    3D effect is achieved with layered radial gradients:
        1. Base sphere gradient (light side → dark side)
        2. Atmosphere/rim glow
        3. Specular highlight (small bright spot)
        4. Shadow terminator (dark edge on the far side from sun)

    Replace everything from the top of main.js to the DOM REFERENCES section.
*/

const canvas = document.getElementById('solar-system');
const ctx = canvas.getContext('2d');
let isPremium = false;
let time = 0;

/* ─── SIZE RATIOS (square-root compressed) ────────────────────────────
   Earth = 1.0 base. We use sqrt() to compress the huge range
   between Mercury and Jupiter into something visible on screen.
   
   Base pixel size = 3.5px (Earth's radius on screen)
   Sun uses a separate larger scale.
*/

const BASE_SIZE = 6;

function sizeOf(earthRatio) {
    return Math.sqrt(earthRatio) * BASE_SIZE;
}

/* Sun position (proportional to canvas) */
const sunPos = { xRatio: 0.12, yRatio: 0.32 };
const SUN_RADIUS = 25;  /* Compressed — real ratio would be 109x Earth */

/* ─── PLANET DATA ─────────────────────────────────────────────────────
   Each planet has:
     name        — for reference
     sizeRatio   — real diameter ratio to Earth
     orbitA/B    — semi-major/minor axes (proportion of canvas width/height)
     speed       — orbital speed (radians per frame)
     offset      — starting angle
     colors      — { base, light, dark, atmosphere } for 3D rendering
*/

const planets = [
    {
        name: 'Mercury',
        sizeRatio: 0.38,
        orbitA: 0.07, orbitB: 0.045,
        speed: 0.009, offset: 0.4,
        colors: {
            base: [169, 169, 169],     /* Gray */
            light: [200, 200, 200],
            dark: [80, 80, 80],
            atmosphere: null
        }
    },
    {
        name: 'Venus',
        sizeRatio: 0.95,
        orbitA: 0.12, orbitB: 0.075,
        speed: 0.006, offset: 2.1,
        colors: {
            base: [222, 184, 135],     /* Pale yellowish */
            light: [245, 222, 179],
            dark: [160, 120, 60],
            atmosphere: [255, 240, 200, 0.15]
        }
    },
    {
        name: 'Earth',
        sizeRatio: 1.0,
        orbitA: 0.18, orbitB: 0.10,
        speed: 0.004, offset: 4.2,
        colors: {
            base: [70, 130, 200],      /* Blue */
            light: [100, 170, 240],
            dark: [20, 50, 100],
            atmosphere: [130, 200, 255, 0.12]
        }
    },
    {
        name: 'Mars',
        sizeRatio: 0.53,
        orbitA: 0.25, orbitB: 0.14,
        speed: 0.003, offset: 1.0,
        colors: {
            base: [193, 68, 14],       /* Red-orange */
            light: [220, 100, 50],
            dark: [100, 30, 5],
            atmosphere: null
        }
    },
    {
        name: 'Jupiter',
        sizeRatio: 11.2,
        orbitA: 0.38, orbitB: 0.20,
        speed: 0.0015, offset: 3.5,
        colors: {
            base: [200, 139, 58],      /* Orange-brown */
            light: [235, 190, 120],
            dark: [120, 70, 20],
            atmosphere: [255, 200, 130, 0.08]
        }
    },
    {
        name: 'Saturn',
        sizeRatio: 9.45,
        orbitA: 0.52, orbitB: 0.27,
        speed: 0.001, offset: 5.8,
        colors: {
            base: [218, 195, 132],     /* Golden */
            light: [245, 230, 180],
            dark: [140, 120, 60],
            atmosphere: [255, 230, 160, 0.06],
            rings: true                /* Saturn gets rings */
        }
    },
];


function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}


/* ─── 3D PLANET RENDERER ──────────────────────────────────────────────
   Draws a single planet with realistic 3D shading.

   The 3D effect uses multiple gradient layers:
   1. Base sphere: radial gradient offset toward the sun (light source)
      to create the illusion of a lit sphere
   2. Shadow terminator: darker edge on the side away from the sun
   3. Atmosphere glow: faint colored halo around planets that have one
   4. Specular highlight: small bright dot where light hits directly
*/

function drawPlanet(px, py, radius, colors, sunX, sunY, alpha) {
    if (radius < 0.5) return;  /* Skip if too tiny to see */

    /* Direction from planet to sun (for lighting) */
    const dx = sunX - px;
    const dy = sunY - py;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const lightDirX = dx / dist;
    const lightDirY = dy / dist;

    /* Offset the gradient center toward the light source */
    const highlightX = px + lightDirX * radius * 0.35;
    const highlightY = py + lightDirY * radius * 0.35;

    /* 1. Base sphere gradient */
    const baseGrad = ctx.createRadialGradient(
        highlightX, highlightY, radius * 0.05,
        px, py, radius
    );
    baseGrad.addColorStop(0, `rgba(${colors.light[0]}, ${colors.light[1]}, ${colors.light[2]}, ${alpha})`);
    baseGrad.addColorStop(0.5, `rgba(${colors.base[0]}, ${colors.base[1]}, ${colors.base[2]}, ${alpha})`);
    baseGrad.addColorStop(1, `rgba(${colors.dark[0]}, ${colors.dark[1]}, ${colors.dark[2]}, ${alpha})`);

    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);
    ctx.fillStyle = baseGrad;
    ctx.fill();

    /* 2. Shadow terminator — extra dark on the far side from sun */
    const shadowX = px - lightDirX * radius * 0.3;
    const shadowY = py - lightDirY * radius * 0.3;
    const shadowGrad = ctx.createRadialGradient(
        shadowX, shadowY, radius * 0.5,
        shadowX, shadowY, radius * 1.2
    );
    shadowGrad.addColorStop(0, 'rgba(0, 0, 0, 0)');
    shadowGrad.addColorStop(1, `rgba(0, 0, 0, ${alpha * 0.4})`);

    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);
    ctx.fillStyle = shadowGrad;
    ctx.fill();

    /* 3. Specular highlight — tiny bright spot */
    const specX = highlightX;
    const specY = highlightY;
    const specSize = radius * 0.25;
    const specGrad = ctx.createRadialGradient(
        specX, specY, 0,
        specX, specY, specSize
    );
    specGrad.addColorStop(0, `rgba(255, 255, 255, ${alpha * 0.5})`);
    specGrad.addColorStop(1, `rgba(255, 255, 255, 0)`);

    ctx.beginPath();
    ctx.arc(specX, specY, specSize, 0, Math.PI * 2);
    ctx.fillStyle = specGrad;
    ctx.fill();

    /* 4. Atmosphere glow (if planet has one) */
    if (colors.atmosphere) {
        const atm = colors.atmosphere;
        const atmGrad = ctx.createRadialGradient(
            px, py, radius * 0.85,
            px, py, radius * 1.4
        );
        atmGrad.addColorStop(0, `rgba(${atm[0]}, ${atm[1]}, ${atm[2]}, ${atm[3] * alpha})`);
        atmGrad.addColorStop(1, `rgba(${atm[0]}, ${atm[1]}, ${atm[2]}, 0)`);

        ctx.beginPath();
        ctx.arc(px, py, radius * 1.4, 0, Math.PI * 2);
        ctx.fillStyle = atmGrad;
        ctx.fill();
    }
}


/* ─── SATURN'S RINGS ──────────────────────────────────────────────────
   Drawn as a tilted ellipse around Saturn using arc + scale transform.
*/

function drawRings(px, py, planetRadius, sunX, sunY, alpha) {
    const ringInner = planetRadius * 1.4;
    const ringOuter = planetRadius * 2.2;

    ctx.save();
    ctx.translate(px, py);
    /* Tilt the rings ~25 degrees */
    ctx.scale(1, 0.35);

    /* Ring band */
    for (let r = ringInner; r < ringOuter; r += 1.5) {
        const progress = (r - ringInner) / (ringOuter - ringInner);
        /* Rings have gaps — vary opacity to simulate Cassini division */
        let ringAlpha = alpha * 0.3;
        if (progress > 0.35 && progress < 0.45) ringAlpha *= 0.2;  /* Cassini gap */

        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(210, 190, 140, ${ringAlpha})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
    }

    ctx.restore();
}


/* ─── DRAW SUN ────────────────────────────────────────────────────────
   Multi-layered glow effect for a realistic sun.
*/

function drawSun(sunX, sunY, alpha) {
    const pulse = 1 + Math.sin(time * 0.015) * 0.08;
    const r = SUN_RADIUS * pulse;

    /* Outer corona */
    const corona = ctx.createRadialGradient(sunX, sunY, r * 0.5, sunX, sunY, r * 4);
    corona.addColorStop(0, `rgba(255, 200, 50, ${alpha * 0.08})`);
    corona.addColorStop(0.5, `rgba(255, 160, 30, ${alpha * 0.02})`);
    corona.addColorStop(1, 'rgba(255, 140, 20, 0)');
    ctx.fillStyle = corona;
    ctx.beginPath();
    ctx.arc(sunX, sunY, r * 4, 0, Math.PI * 2);
    ctx.fill();

    /* Middle glow */
    const midGlow = ctx.createRadialGradient(sunX, sunY, 0, sunX, sunY, r * 2);
    midGlow.addColorStop(0, `rgba(255, 230, 130, ${alpha * 0.3})`);
    midGlow.addColorStop(0.4, `rgba(255, 180, 50, ${alpha * 0.12})`);
    midGlow.addColorStop(1, 'rgba(255, 150, 30, 0)');
    ctx.fillStyle = midGlow;
    ctx.beginPath();
    ctx.arc(sunX, sunY, r * 2, 0, Math.PI * 2);
    ctx.fill();

    /* Core */
    const coreGrad = ctx.createRadialGradient(
        sunX - r * 0.15, sunY - r * 0.15, 0,
        sunX, sunY, r
    );
    coreGrad.addColorStop(0, `rgba(255, 255, 220, ${alpha * 0.95})`);
    coreGrad.addColorStop(0.3, `rgba(255, 220, 100, ${alpha * 0.8})`);
    coreGrad.addColorStop(0.7, `rgba(255, 170, 40, ${alpha * 0.6})`);
    coreGrad.addColorStop(1, `rgba(220, 120, 20, ${alpha * 0.3})`);
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(sunX, sunY, r, 0, Math.PI * 2);
    ctx.fill();

    /* Hot spot */
    const hot = ctx.createRadialGradient(
        sunX - r * 0.2, sunY - r * 0.2, 0,
        sunX, sunY, r * 0.5
    );
    hot.addColorStop(0, `rgba(255, 255, 255, ${alpha * 0.6})`);
    hot.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = hot;
    ctx.beginPath();
    ctx.arc(sunX - r * 0.2, sunY - r * 0.2, r * 0.5, 0, Math.PI * 2);
    ctx.fill();
}


/* ─── MAIN DRAW LOOP ─────────────────────────────────────────────── */

function drawSolarSystem() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const sunX = canvas.width * sunPos.xRatio;
    const sunY = canvas.height * sunPos.yRatio;
    const alpha = isPremium ? 0.85 : 0.5;

    /* Draw sun */
    drawSun(sunX, sunY, alpha);

    /* Draw orbits and planets */
    for (const p of planets) {
        const a = p.orbitA * canvas.width;
        const b = p.orbitB * canvas.height;
        const angle = p.offset + time * p.speed;
        const radius = sizeOf(p.sizeRatio);

        /* Orbit ring (faint ellipse) */
        ctx.beginPath();
        ctx.ellipse(sunX, sunY, a, b, 0, 0, Math.PI * 2);
        ctx.strokeStyle = isPremium
            ? 'rgba(255, 200, 100, 0.04)'
            : 'rgba(160, 120, 60, 0.03)';
        ctx.lineWidth = 0.8;
        ctx.stroke();

        /* Planet position on orbit */
        const px = sunX + Math.cos(angle) * a;
        const py = sunY + Math.sin(angle) * b;

        /* Draw Saturn's rings BEHIND the planet (back half) */
        if (p.colors.rings) {
            drawRings(px, py, radius, sunX, sunY, alpha);
        }

        /* Draw the planet */
        drawPlanet(px, py, radius, p.colors, sunX, sunY, alpha);
    }

    time++;
    requestAnimationFrame(drawSolarSystem);
}

/* Start */
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
const VOICE_MAX_WORDS = 500;
const VOICE_MAX_CHARS = 5000;
const INPUT_MIN_WORDS = 100;
const INPUT_MIN_CHARS = 1000;
const INPUT_MAX_WORDS = 500;
const INPUT_MAX_CHARS = 5000;

let lastRequestTime = 0;
const REQUEST_COOLDOWN = 3000;  /* 3 seconds between requests */

document.querySelector('.btn-text').textContent = 'Quick Fix';


/* ═══════════════════════════════════════════════════════════════════
   3. CHARACTER COUNTERS — both panels
   ═══════════════════════════════════════════════════════════════════ */

inputText.addEventListener('input', function () {
    let text = this.value;

    /* Silently truncate to max chars */
    if (text.length > INPUT_MAX_CHARS) {
        text = text.substring(0, INPUT_MAX_CHARS);
        /* Cut at last sentence boundary within limit */
        const lastPeriod = text.lastIndexOf('.');
        const lastQuestion = text.lastIndexOf('?');
        const lastExclaim = text.lastIndexOf('!');
        const lastSentence = Math.max(lastPeriod, lastQuestion, lastExclaim);
        if (lastSentence > INPUT_MAX_CHARS * 0.5) {
            text = text.substring(0, lastSentence + 1);
        }
        this.value = text;
    }

    /* Also check word limit */
    const wordsArr = text.trim() ? text.trim().split(/\s+/) : [];
    if (wordsArr.length > INPUT_MAX_WORDS) {
        /* Find the position after the 500th word */
        let count = 0;
        let cutIndex = 0;
        for (let i = 0; i < text.length; i++) {
            if (/\s/.test(text[i]) && i > 0 && !/\s/.test(text[i - 1])) {
                count++;
                if (count >= INPUT_MAX_WORDS) {
                    cutIndex = i;
                    break;
                }
            }
        }
        if (cutIndex > 0) {
            text = text.substring(0, cutIndex);
            /* Cut at last sentence boundary */
            const lastPeriod = text.lastIndexOf('.');
            const lastQuestion = text.lastIndexOf('?');
            const lastExclaim = text.lastIndexOf('!');
            const lastSentence = Math.max(lastPeriod, lastQuestion, lastExclaim);
            if (lastSentence > text.length * 0.5) {
                text = text.substring(0, lastSentence + 1);
            }
            this.value = text;
        }
    }

    const trimmed = this.value.trim();
    const len = trimmed.length;
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
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
    let text = this.value;

    /* Silently truncate to max chars */
    if (text.length > VOICE_MAX_CHARS) {
        text = text.substring(0, VOICE_MAX_CHARS);
        const lastPeriod = text.lastIndexOf('.');
        const lastQuestion = text.lastIndexOf('?');
        const lastExclaim = text.lastIndexOf('!');
        const lastSentence = Math.max(lastPeriod, lastQuestion, lastExclaim);
        if (lastSentence > VOICE_MAX_CHARS * 0.5) {
            text = text.substring(0, lastSentence + 1);
        }
        this.value = text;
    }

    /* Also check word limit */
    const wordsArr = text.trim() ? text.trim().split(/\s+/) : [];
    if (wordsArr.length > VOICE_MAX_WORDS) {
        let count = 0;
        let cutIndex = 0;
        for (let i = 0; i < text.length; i++) {
            if (/\s/.test(text[i]) && i > 0 && !/\s/.test(text[i - 1])) {
                count++;
                if (count >= VOICE_MAX_WORDS) {
                    cutIndex = i;
                    break;
                }
            }
        }
        if (cutIndex > 0) {
            text = text.substring(0, cutIndex);
            const lastPeriod = text.lastIndexOf('.');
            const lastQuestion = text.lastIndexOf('?');
            const lastExclaim = text.lastIndexOf('!');
            const lastSentence = Math.max(lastPeriod, lastQuestion, lastExclaim);
            if (lastSentence > text.length * 0.5) {
                text = text.substring(0, lastSentence + 1);
            }
            this.value = text;
        }
    }

    const trimmed = this.value.trim();
    const len = trimmed.length;
    const words = trimmed ? trimmed.split(/\s+/).length : 0;

    voiceCount.textContent = `${words.toLocaleString()} words · ${len.toLocaleString()} chars`;

    if (words >= VOICE_MIN_WORDS && len >= VOICE_MIN_CHARS) {
        voiceCount.classList.add('valid');
    } else {
        voiceCount.classList.remove('valid');
    }
});

/**
 * Check if voice sample is valid.
 * Returns:
 *   ''    — no sample provided (or toggle is off) — use default style
 *   text  — valid sample text — use voice matching
 *   null  — sample exists but too short — show error
 */
function getVoiceSample() {
    /* Voice matching only works in Deep Rewrite mode */
    if (!toggleDeep.checked) return '';

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

    /* Prevent rapid clicking */
    const now = Date.now();
    if (now - lastRequestTime < REQUEST_COOLDOWN) {
        showToast('Please wait a moment before trying again.');
        return;
    }
    lastRequestTime = now;

    showLoading();

    try {
        const result = await callAPI(text);
        showResult(result);
    } catch (error) {
        console.error('Rewrite failed:', error);
        showError(
            error.message,
            error.flaggedWords || null,
            error.field || 'input'
        );
    }
});


/* ═══════════════════════════════════════════════════════════════════
   6. API CALL
   ═══════════════════════════════════════════════════════════════════ */

   /**
 * Get Django's CSRF token from cookies.
 * Django sets a cookie called 'csrftoken' — we read it and send
 * it back in the X-CSRFToken header with every POST request.
 *
 * @returns {string} The CSRF token value
 */
function getCSRFToken() {
    /* Try cookie first */
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith('csrftoken=')) {
            return cookie.substring('csrftoken='.length);
        }
    }
    /* Fallback to meta tag */
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

async function callAPI(text) {
    const deepRewrite = toggleDeep.checked;
    /* Validate input minimum */
    const inputWords = text.trim().split(/\s+/).length;
    const inputChars = text.trim().length;

    if (inputWords < INPUT_MIN_WORDS || inputChars < INPUT_MIN_CHARS) {
        throw new Error(
            `Text too short: ${inputWords} words / ${inputChars} chars. ` +
            `Need at least ${INPUT_MIN_WORDS} words and ${INPUT_MIN_CHARS} chars.`
        );
    }
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
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({
            text,
            deep_rewrite: deepRewrite,
            voice_sample: voiceSampleText,
        }),
    });

    const data = await response.json();
    if (!response.ok) {
        const err = new Error(data.error || 'Something went wrong');
        err.flaggedWords = data.flagged_words || null;
        err.field = data.field || null;
        throw err;
    }
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

    /* Pick loading message based on mode + voice sample */
    let message = 'Applying pattern fixes...';

    if (toggleDeep.checked) {
        const sample = voiceSample.value.trim();
        if (sample.length > 0) {
            message = 'Matching your writing style...';
        } else {
            message = 'Deep Rewriting...';
        }
    }

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
    `;
    resultStats.style.display = 'block';

    btnCopy.style.display = 'flex';
}

function showError(message, flaggedWords, field) {
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

    /* Highlight flagged words in the source textarea */
    if (flaggedWords && flaggedWords.length > 0) {
        if (field === 'input') {
            showInlineHighlights(inputText, flaggedWords);
        } else if (field === 'voice') {
            showInlineHighlights(voiceSample, flaggedWords);
        }
    }
}

/**
 * Temporarily replaces a textarea with a styled div showing
 * flagged words highlighted in red. When the user clicks the
 * div, it swaps back to the textarea for editing.
 *
 * @param {HTMLTextAreaElement} textarea — the textarea to highlight
 * @param {Array} words — list of flagged words
 */
function showInlineHighlights(textarea, words) {
    const text = textarea.value;

    /* Build highlighted HTML */
    let html = escapeHtml(text);
    for (const word of words) {
        const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp('\\b(' + escaped + ')\\b', 'gi');
        html = html.replace(regex, '<span class="flagged-word">$1</span>');
    }

    /* Create a div that looks exactly like the textarea */
    const overlay = document.createElement('div');
    overlay.className = 'highlight-overlay';
    overlay.innerHTML = html;

    /* Match the textarea's actual height */
    overlay.style.height = textarea.offsetHeight + 'px';

    /* Hide textarea, show overlay in its place */
    textarea.style.display = 'none';
    textarea.parentElement.insertBefore(overlay, textarea);

    /* Click overlay to go back to editing */
    overlay.addEventListener('click', function () {
        overlay.remove();
        textarea.style.display = '';
        textarea.focus();
    });
}


/* ═══════════════════════════════════════════════════════════════════
   8. CHANGES REPORT — COLLAPSIBLE
   ═══════════════════════════════════════════════════════════════════ */

function buildChangesReport(changes) {

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