/*
    main.js
    -------
    Handles all the interactive behaviour on the page.

    Right now the humanize button uses a FAKE response to simulate
    the real API call. In Step 4 we replace the fake response
    with a real fetch() call to our Django backend.

    Structure:
    1. Get references to DOM elements
    2. Update character count as user types
    3. Handle the Humanize button click
    4. Show loading state
    5. Show result (fake for now)
    6. Handle Copy button
    7. Show toast notifications
*/


/* ─── 1. DOM ELEMENT REFERENCES ─────────────────────────────────────────────

   We grab references to HTML elements once at the top.
   This is faster than searching the DOM every time we need them.
   document.getElementById() finds an element by its id="..." attribute.
*/
const inputText      = document.getElementById('input-text');
const outputArea     = document.getElementById('output-area');
const charCount      = document.getElementById('char-count');
const btnHumanize    = document.getElementById('btn-humanize');
const btnCopy        = document.getElementById('btn-copy');
const toast          = document.getElementById('toast');


/* ─── 2. CHARACTER COUNTER ───────────────────────────────────────────────────

   Updates the character count display as the user types.
   'input' event fires every time the textarea content changes.
*/
inputText.addEventListener('input', function() {
    /*
     * this.value is the current text in the textarea.
     * .length gives the number of characters.
     */
    const count = this.value.length;
    charCount.textContent = count.toLocaleString() + ' characters';

    /*
     * Disable the Humanize button if there is no text.
     * This prevents the user from clicking it on an empty input.
     */
    btnHumanize.disabled = count === 0;
});


/* ─── 3. HUMANIZE BUTTON CLICK ───────────────────────────────────────────────

   This is the main function. When the user clicks Humanize:
   1. Validate they typed something
   2. Show the loading state
   3. Call the humanize function (fake for now, real in Step 4)
   4. Show the result
*/
btnHumanize.addEventListener('click', async function() {
    /*
     * Get the text the user typed.
     * .trim() removes whitespace from the start and end.
     */
    const text = inputText.value.trim();

    /* Guard clause: do nothing if the input is empty */
    if (!text) return;

    /* Show loading animation in the output panel */
    showLoading();

    try {
        /*
         * Call our humanize function.
         * 'await' pauses here until the function finishes.
         * In Step 4, this will be a real API call.
         * Right now it returns a fake result after a delay.
         */
        const result = await humanizeText(text);

        /* Show the result in the output panel */
        showResult(result);

    } catch (error) {
        /*
         * If anything goes wrong, show an error message.
         * console.error() logs the full error for debugging.
         */
        console.error('Humanization failed:', error);
        showError(error.message);
    }
});


/* ─── 4. HUMANIZE FUNCTION (FAKE / PLACEHOLDER) ──────────────────────────────

   This function simulates what the real API call will do.
   It waits 2 seconds (like a real API would take) then returns
   a hardcoded example result.

   In Step 4 we replace the body of this function with:
       const response = await fetch('/api/humanize/', {...})

   Inputs:  text (string) - the AI-generated text to humanize
   Outputs: Promise<string> - the humanized text (or throws an error)
*/
async function humanizeText(text) {
    /*
     * Simulate network delay so we can see the loading state.
     * Promise + setTimeout is the standard way to fake async waits.
     * 2000 = 2000 milliseconds = 2 seconds.
     */
    await new Promise(resolve => setTimeout(resolve, 2000));

    /*
     * Return a fake result for now.
     * This is just a demonstration so you can see the UI working.
     * The real result will come from GPT-4o mini via our Django backend.
     */
    return `This is a placeholder humanized version of your text.

In Step 4, this will be replaced with the actual GPT-4o mini response that rewrites your AI-generated text using the 29 humanizer patterns.

Your original text was ${text.split(' ').length} words long.`;
}


/* ─── 5. UI STATE FUNCTIONS ──────────────────────────────────────────────────

   These functions swap what is shown inside the output panel.
   The output panel can show one of four states:
   - Placeholder (default, before anything happens)
   - Loading (while waiting for API)
   - Result (after success)
   - Error (if something went wrong)
*/

/**
 * Shows the three-dot loading animation in the output panel.
 * Called when the Humanize button is clicked.
 */
function showLoading() {
    /* Disable the button to prevent double-clicks */
    btnHumanize.disabled = true;
    btnHumanize.textContent = 'Humanizing...';

    /* Replace the output panel content with a loading animation */
    outputArea.innerHTML = `
        <div class="loading-state">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <p>Rewriting your text...</p>
        </div>
    `;
}

/**
 * Shows the humanized result text in the output panel.
 * Called when the API call succeeds.
 *
 * @param {string} text - The humanized text to display
 */
function showResult(text) {
    /* Re-enable the button */
    btnHumanize.disabled = false;
    btnHumanize.innerHTML = '✦ Humanize';

    /* Show the humanized text */
    outputArea.innerHTML = `<div id="output-text">${escapeHtml(text)}</div>`;

    /* Show the Copy button */
    btnCopy.style.display = 'inline-flex';
}

/**
 * Shows an error message in the output panel.
 * Called when the API call fails.
 *
 * @param {string} message - The error message to show the user
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

/**
 * Sanitizes text before inserting it into HTML.
 * Prevents XSS attacks where malicious text could inject HTML tags.
 * Always sanitize user input before putting it in the DOM.
 *
 * @param {string} text - Raw text to sanitize
 * @returns {string} - Safe HTML string
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}


/* ─── 6. COPY BUTTON ─────────────────────────────────────────────────────────

   Copies the output text to the clipboard when the user clicks Copy.
   Uses the modern Clipboard API.
*/
btnCopy.addEventListener('click', async function() {
    /* Find the output text element */
    const outputText = document.getElementById('output-text');
    if (!outputText) return;

    try {
        /*
         * navigator.clipboard.writeText() copies to clipboard.
         * It returns a Promise, so we await it.
         */
        await navigator.clipboard.writeText(outputText.textContent);
        showToast('Copied to clipboard!');
    } catch (error) {
        showToast('Could not copy. Please select and copy manually.');
    }
});


/* ─── 7. TOAST NOTIFICATION ──────────────────────────────────────────────────

   Shows a small popup message at the bottom right of the screen.
   Automatically hides after 2.5 seconds.

   @param {string} message - The message to show in the toast
*/
function showToast(message) {
    toast.textContent = message;

    /* Add the 'show' class to trigger the CSS transition (fade in) */
    toast.classList.add('show');

    /* After 2.5 seconds, remove 'show' to fade out */
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2500);
}