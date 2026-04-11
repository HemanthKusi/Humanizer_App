/*
    main.js
    -------
    Handles all interactive behaviour on the page.

    NOW UPDATED: The humanize button calls our real Django backend
    at /api/humanize/ which runs the rule-based pattern engine.

    Structure:
    1. DOM element references
    2. Character counter
    3. Humanize button click handler
    4. humanizeText() — real API call to Django backend
    5. UI state functions (loading, result, error)
    6. Changes report display
    7. Copy button
    8. Toast notifications
*/


/* ─── 1. DOM ELEMENT REFERENCES ──────────────────────────────────────────── */

const inputText      = document.getElementById('input-text');
const outputArea     = document.getElementById('output-area');
const charCount      = document.getElementById('char-count');
const btnHumanize    = document.getElementById('btn-humanize');
const btnCopy        = document.getElementById('btn-copy');
const toast          = document.getElementById('toast');


/* ─── 2. CHARACTER COUNTER ───────────────────────────────────────────────── */

inputText.addEventListener('input', function() {
    const count = this.value.length;
    charCount.textContent = count.toLocaleString() + ' characters';
    btnHumanize.disabled = count === 0;
});


/* ─── 3. HUMANIZE BUTTON CLICK ───────────────────────────────────────────── */

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


/* ─── 4. HUMANIZE FUNCTION — REAL API CALL ───────────────────────────────── 

   Sends the user's text to our Django backend at /api/humanize/
   The backend runs the rule-based engine and returns JSON.

   Inputs:  text (string) — the AI-generated text to humanize
   Outputs: Promise<object> — { text, changes, stats, mode }
   Throws:  Error if the request fails or the server returns an error
*/
async function humanizeText(text) {
    /*
     * fetch() sends an HTTP request to our Django backend.
     *
     * method: 'POST' — we're sending data to the server
     * headers: tells the server we're sending JSON
     * body: the actual data — our text wrapped in a JSON object
     */
    const response = await fetch('/api/humanize/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text }),
    });

    /*
     * Parse the JSON response from the server.
     * This gives us an object like:
     * { text: "...", changes: [...], stats: {...}, mode: "rule-based" }
     */
    const data = await response.json();

    /*
     * If the server returned an error (status 400 or 500),
     * throw it so our catch block in the click handler catches it.
     */
    if (!response.ok) {
        throw new Error(data.error || 'Something went wrong');
    }

    return data;
}


/* ─── 5. UI STATE FUNCTIONS ──────────────────────────────────────────────── */

/**
 * Shows the loading animation in the output panel.
 */
function showLoading() {
    btnHumanize.disabled = true;
    btnHumanize.textContent = 'Humanizing...';
    btnCopy.style.display = 'none';

    outputArea.innerHTML = `
        <div class="loading-state">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <p>Analyzing patterns...</p>
        </div>
    `;
}

/**
 * Shows the humanized result text and the changes report.
 *
 * @param {object} result — { text, changes, stats, mode }
 */
function showResult(result) {
    btnHumanize.disabled = false;
    btnHumanize.innerHTML = '✦ Humanize';

    /* Build the output HTML */
    let html = `<div id="output-text">${escapeHtml(result.text)}</div>`;

    /* Add the stats bar */
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

    /* Add the changes report if there are changes */
    if (result.changes && result.changes.length > 0) {
        html += buildChangesReport(result.changes);
    }

    outputArea.innerHTML = html;
    btnCopy.style.display = 'inline-flex';
}

/**
 * Shows an error message in the output panel.
 *
 * @param {string} message — The error message to display
 */
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


/* ─── 6. CHANGES REPORT ─────────────────────────────────────────────────── 

   Builds an HTML list showing what patterns were detected and changed.
   This helps the user understand what the engine did to their text.

   @param {Array} changes — list of { pattern, name, detail } objects
   @returns {string} — HTML string for the changes report
*/
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
            <div class="changes-header">Changes made</div>
            ${items}
        </div>
    `;
}


/**
 * Sanitizes text before inserting into HTML to prevent XSS.
 *
 * @param {string} text — Raw text to sanitize
 * @returns {string} — Safe HTML string
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}


/* ─── 7. COPY BUTTON ─────────────────────────────────────────────────────── */

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


/* ─── 8. TOAST NOTIFICATION ──────────────────────────────────────────────── */

function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2500);
}