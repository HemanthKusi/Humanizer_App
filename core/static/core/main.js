/*
    main.js
    -------
    Handles all interactive behaviour on the page.

    UPDATED IN STEP 5:
    - Reads the Deep Rewrite toggle state
    - Sends deep_rewrite flag to the backend
    - Updates toggle label text
    - Shows warning messages if LLM fails

    Structure:
    1. DOM element references
    2. Character counter
    3. Toggle switch behavior
    4. Humanize button click handler
    5. humanizeText() — API call with toggle support
    6. UI state functions
    7. Changes report
    8. Copy button
    9. Toast notifications
*/


/* ─── 1. DOM ELEMENT REFERENCES ──────────────────────────────────────────── */

const inputText      = document.getElementById('input-text');
const outputArea     = document.getElementById('output-area');
const charCount      = document.getElementById('char-count');
const btnHumanize    = document.getElementById('btn-humanize');
const btnCopy        = document.getElementById('btn-copy');
const toast          = document.getElementById('toast');
const toggleDeep     = document.getElementById('toggle-deep');
const toggleLabel    = document.getElementById('toggle-label');


/* ─── 2. CHARACTER COUNTER ───────────────────────────────────────────────── */

inputText.addEventListener('input', function() {
    const count = this.value.length;
    charCount.textContent = count.toLocaleString() + ' characters';
    btnHumanize.disabled = count === 0;
});


/* ─── 3. TOGGLE SWITCH BEHAVIOR ──────────────────────────────────────────── 

   When the toggle changes, update the label text so the user
   knows which mode they're in.
   
   OFF = "Quick fix"    (rule-based only, instant, free)
   ON  = "Deep rewrite" (LLM, 2-5 sec, costs ~$0.002)
*/

toggleDeep.addEventListener('change', function() {
    if (this.checked) {
        toggleLabel.textContent = 'Deep rewrite';
        toggleLabel.style.color = 'var(--accent)';
    } else {
        toggleLabel.textContent = 'Quick fix';
        toggleLabel.style.color = 'var(--text-muted)';
    }
});


/* ─── 4. HUMANIZE BUTTON CLICK ───────────────────────────────────────────── */

btnHumanize.addEventListener('click', async function() {
    const text = inputText.value.trim();
    if (!text) return;

    showLoading();

    try {
        const result = await humanizeText(text);
        showResult(result);
    } catch (error) {
        console.error('Humanization failed:', error);
        showError(error.message);
    }
});


/* ─── 5. HUMANIZE FUNCTION — API CALL WITH TOGGLE ────────────────────────── 

   Sends the user's text to /api/humanize/ along with the toggle state.

   Inputs:  text (string) — the AI-generated text
   Outputs: Promise<object> — { text, changes, stats, mode, warning? }
   Throws:  Error if the request fails
*/
async function humanizeText(text) {
    /*
     * Read whether the Deep Rewrite toggle is ON or OFF.
     * .checked is a boolean: true if ON, false if OFF.
     */
    const deepRewrite = toggleDeep.checked;

    const response = await fetch('/api/humanize/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text: text,
            deep_rewrite: deepRewrite,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Something went wrong');
    }

    return data;
}


/* ─── 6. UI STATE FUNCTIONS ──────────────────────────────────────────────── */

function showLoading() {
    btnHumanize.disabled = true;
    btnHumanize.textContent = 'Humanizing...';
    btnCopy.style.display = 'none';

    /*
     * Show different loading message based on toggle state.
     * Deep rewrite takes longer, so we set user expectations.
     */
    const message = toggleDeep.checked
        ? 'Deep rewriting with AI... (this takes a few seconds)'
        : 'Analyzing patterns...';

    outputArea.innerHTML = `
        <div class="loading-state">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <p>${message}</p>
        </div>
    `;
}

/**
 * Shows the humanized result text, stats, changes, and any warnings.
 *
 * @param {object} result — { text, changes, stats, mode, warning? }
 */
function showResult(result) {
    btnHumanize.disabled = false;
    btnHumanize.innerHTML = '✦ Humanize';

    /* Build the output HTML */
    let html = `<div id="output-text">${escapeHtml(result.text)}</div>`;

    /* Show warning if LLM failed and we fell back to rule-based */
    if (result.warning) {
        html += `
            <div class="warning-bar">
                ⚠️ ${escapeHtml(result.warning)}
            </div>
        `;
    }

    /* Stats bar */
    html += `
        <div class="stats-bar" style="display: flex;">
            <div class="stat">
                <span class="stat-label">Words</span>
                <span class="stat-value">${result.stats.original_words} → ${result.stats.final_words}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Patterns found</span>
                <span class="stat-value">${result.stats.patterns_found}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Mode</span>
                <span class="stat-value">${result.mode}</span>
            </div>
        </div>
    `;

    /* Changes report */
    if (result.changes && result.changes.length > 0) {
        html += buildChangesReport(result.changes);
    }

    outputArea.innerHTML = html;
    btnCopy.style.display = 'inline-flex';
}

function showError(message) {
    btnHumanize.disabled = false;
    btnHumanize.innerHTML = '✦ Humanize';

    outputArea.innerHTML = `
        <div class="output-placeholder" style="color: var(--error);">
            <div class="output-placeholder-icon">⚠️</div>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
}


/* ─── 7. CHANGES REPORT ─────────────────────────────────────────────────── */

function buildChangesReport(changes) {
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

    return `
        <div class="changes-report">
            <div class="changes-header">Changes made (rule-based pre-processing)</div>
            ${items}
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}


/* ─── 8. COPY BUTTON ─────────────────────────────────────────────────────── */

btnCopy.addEventListener('click', async function() {
    const outputText = document.getElementById('output-text');
    if (!outputText) return;

    try {
        await navigator.clipboard.writeText(outputText.textContent);
        showToast('Copied to clipboard!');
    } catch (error) {
        showToast('Could not copy. Please select and copy manually.');
    }
});


/* ─── 9. TOAST NOTIFICATION ──────────────────────────────────────────────── */

function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2500);
}