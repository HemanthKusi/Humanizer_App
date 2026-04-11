"""
core/humanizer_engine.py
------------------------
Rule-based AI text humanizer engine (Layer 1 of the hybrid approach).

This module detects and fixes common AI writing patterns using regex
and word lists. It does NOT call any external API — everything runs
locally, instantly, and for free.

Based on the 29 patterns from SKILL.md (Wikipedia's "Signs of AI writing").

How it works:
    1. Text comes in as a string
    2. It passes through a pipeline of pattern-fixing functions
    3. Each function looks for one category of AI patterns
    4. Each function returns the fixed text + a list of changes it made
    5. At the end, you get back the fully cleaned text + all changes

Usage:
    from core.humanizer_engine import humanize_rule_based

    result = humanize_rule_based("Your AI-generated text here...")
    print(result['text'])       # The cleaned text
    print(result['changes'])    # List of changes made
    print(result['stats'])      # Summary statistics
"""

import re


# ─── PATTERN DEFINITIONS ────────────────────────────────────────────────────
#
# Each pattern category has:
#   - A name (shown to the user in the changes report)
#   - A pattern number (matching SKILL.md numbering)
#   - The actual regex or word list used to detect it
#   - The replacement logic


# Pattern 23: Filler phrases that can be simplified
# These are phrases where a shorter version means exactly the same thing.
# The key is the filler phrase (lowercase), the value is the replacement.
FILLER_PHRASES = {
    "in order to":                    "to",
    "due to the fact that":           "because",
    "at this point in time":          "now",
    "in the event that":              "if",
    "has the ability to":             "can",
    "it is important to note that":   "",       # just remove it
    "it is worth noting that":        "",
    "it should be noted that":        "",
    "it is worth mentioning that":    "",
    "it goes without saying that":    "",
    "needless to say":                "",
    "as a matter of fact":            "in fact",
    "in light of the fact that":      "because",
    "for the purpose of":             "to",
    "with regard to":                 "about",
    "with respect to":                "about",
    "in terms of":                    "for",
    "on the other hand":              "but",
    "at the end of the day":          "",
    "when all is said and done":      "",
    "by virtue of":                   "because of",
    "in the midst of":                "during",
    "in the process of":              "",
    "a wide range of":                "many",
    "a variety of":                   "various",
    "the vast majority of":           "most",
    "each and every":                 "every",
    "first and foremost":             "first",
}


# Pattern 8: Copula avoidance — AI avoids simple "is/are/has"
# These are phrases where AI uses fancy verbs instead of simple ones.
# Key = AI phrase, Value = simpler replacement
COPULA_REPLACEMENTS = {
    "serves as":       "is",
    "stands as":       "is",
    "functions as":    "is",
    "acts as":         "is",
    "operates as":     "is",
    "represents":      "is",
    "constitutes":     "is",
    "boasts":          "has",
    "features":        "has",
    "offers":          "has",
    "encompasses":     "includes",
}


# Pattern 7: Overused AI vocabulary words
# These words appear far more in AI text than human text.
# We don't blindly replace them — we flag them and offer alternatives.
# Some can be auto-replaced, others just get flagged.
AI_VOCABULARY_REPLACEMENTS = {
    "additionally":    "also",
    "furthermore":     "also",
    "moreover":        "also",
    "consequently":    "so",
    "subsequently":    "then",
    "utilize":         "use",
    "utilizing":       "using",
    "utilization":     "use",
    "leverage":        "use",
    "leveraging":      "using",
    "facilitate":      "help",
    "facilitating":    "helping",
    "commence":        "start",
    "commencing":      "starting",
    "endeavor":        "try",
    "endeavors":       "tries",
    "necessitate":     "need",
    "necessitates":    "needs",
    "implement":       "set up",
    "implementing":    "setting up",
    "optimize":        "improve",
    "optimizing":      "improving",
}


# Pattern 7 continued: Words to FLAG (not auto-replace, because context matters)
# These get reported in the changes list so the user knows to review them.
AI_FLAG_WORDS = [
    "delve", "tapestry", "landscape", "pivotal", "crucial",
    "testament", "intricate", "intricacies", "multifaceted",
    "comprehensive", "robust", "nuanced", "paradigm",
    "foster", "fostering", "garner", "garnered",
    "underscore", "underscores", "underscoring",
    "showcase", "showcases", "showcasing",
    "highlight", "highlights", "highlighting",
    "emphasize", "emphasizes", "emphasizing",
    "realm", "sphere", "arena",
    "groundbreaking", "cutting-edge", "state-of-the-art",
    "game-changing", "transformative", "revolutionary",
    "seamless", "streamline", "streamlining",
    "vibrant", "dynamic", "innovative",
    "holistic", "synergy", "ecosystem",
    "empower", "empowering", "empowerment",
]


# Pattern 4: Promotional / advertisement-like words
PROMOTIONAL_WORDS = [
    "breathtaking", "stunning", "remarkable", "extraordinary",
    "unparalleled", "unprecedented", "world-class", "best-in-class",
    "nestled", "in the heart of", "boasts a", "rich tapestry",
    "must-visit", "awe-inspiring", "thought-provoking",
    "renowned", "prestigious", "esteemed",
]


# Pattern 1: Significance inflation phrases
# These puff up importance artificially.
SIGNIFICANCE_PHRASES = [
    r"marking a pivotal moment",
    r"a testament to",
    r"an enduring testament",
    r"underscoring its importance",
    r"highlighting its significance",
    r"setting the stage for",
    r"paving the way for",
    r"a key turning point",
    r"indelible mark",
    r"deeply rooted",
    r"plays a (?:vital|crucial|pivotal|significant|key) role",
    r"represents a (?:significant|major|important) shift",
    r"reflects broader trends",
    r"contributes to the (?:broader|larger|wider)",
]


# Pattern 27: Persuasive authority tropes
AUTHORITY_TROPES = [
    r"the real question is",
    r"at its core",
    r"in reality",
    r"what really matters",
    r"fundamentally",
    r"the deeper issue",
    r"the heart of the matter",
    r"the bottom line is",
    r"what it comes down to",
    r"let'?s be (?:honest|real|clear)",
]


# Pattern 28: Signposting / announcement phrases
SIGNPOSTING_PHRASES = [
    r"let'?s dive in",
    r"let'?s explore",
    r"let'?s break this down",
    r"let'?s take a (?:closer )?look",
    r"let'?s unpack",
    r"let'?s examine",
    r"here'?s what you need to know",
    r"without further ado",
    r"now let'?s (?:look at|turn to|move on to)",
    r"buckle up",
    r"ready\? let'?s go",
]


# ─── PIPELINE FUNCTIONS ─────────────────────────────────────────────────────
#
# Each function takes text + a changes list.
# It modifies the text, appends changes to the list, and returns both.
# This way we can chain them: text flows through each function in order.


def fix_filler_phrases(text, changes):
    """
    Pattern 23: Remove or simplify filler phrases.

    Scans the text for wordy phrases and replaces them with
    shorter equivalents. For example:
        "in order to" → "to"
        "it is important to note that" → (removed)

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    for phrase, replacement in FILLER_PHRASES.items():
        # re.IGNORECASE makes the search case-insensitive
        # re.escape() treats the phrase as literal text, not regex
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        matches = pattern.findall(text)

        if matches:
            # If replacement is empty string, we're removing the phrase
            if replacement:
                text = pattern.sub(replacement, text)
                changes.append({
                    'pattern': 23,
                    'name': 'Filler phrase',
                    'detail': f'"{phrase}" → "{replacement}" ({len(matches)}x)',
                })
            else:
                # Remove the phrase and any trailing space
                text = pattern.sub('', text)
                # Clean up double spaces left behind
                text = re.sub(r'  +', ' ', text)
                changes.append({
                    'pattern': 23,
                    'name': 'Filler phrase removed',
                    'detail': f'Removed "{phrase}" ({len(matches)}x)',
                })

    return text, changes


def fix_copula_avoidance(text, changes):
    """
    Pattern 8: Replace fancy copula-avoiding verbs with simple ones.

    AI text avoids "is" and "has" by using fancier alternatives.
    For example:
        "serves as" → "is"
        "boasts" → "has"

    We use word boundary markers (\\b) to avoid replacing parts of
    longer words. For example, "represents" should match but
    "misrepresents" should not.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    for phrase, replacement in COPULA_REPLACEMENTS.items():
        # \b = word boundary, prevents partial matches
        pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
        matches = pattern.findall(text)

        if matches:
            text = pattern.sub(replacement, text)
            changes.append({
                'pattern': 8,
                'name': 'Copula avoidance',
                'detail': f'"{phrase}" → "{replacement}" ({len(matches)}x)',
            })

    return text, changes


def fix_ai_vocabulary(text, changes):
    """
    Pattern 7: Replace overused AI vocabulary with simpler words.

    AI text uses certain words far more frequently than humans do.
    This function does two things:
    1. Auto-replaces words that have clear simpler alternatives
    2. Flags words that need manual review (context-dependent)

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    # Part 1: Auto-replace words with clear alternatives
    for word, replacement in AI_VOCABULARY_REPLACEMENTS.items():
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        matches = pattern.findall(text)

        if matches:
            # Preserve the original capitalization of the first letter
            def replace_match(match):
                original = match.group(0)
                if original[0].isupper():
                    return replacement.capitalize()
                return replacement

            text = pattern.sub(replace_match, text)
            changes.append({
                'pattern': 7,
                'name': 'AI vocabulary replaced',
                'detail': f'"{word}" → "{replacement}" ({len(matches)}x)',
            })

    # Part 2: Flag words that need manual review
    flagged = []
    for word in AI_FLAG_WORDS:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            flagged.append(f'"{word}" ({len(matches)}x)')

    if flagged:
        changes.append({
            'pattern': 7,
            'name': 'AI vocabulary flagged (review these)',
            'detail': ', '.join(flagged),
        })

    return text, changes


def fix_em_dashes(text, changes):
    """
    Pattern 14: Replace em dashes with commas or periods.

    AI text overuses em dashes (—) to create a punchy, sales-writing feel.
    Most em dashes can be rewritten as commas or separate sentences.

    This function replaces em dashes with commas as a safe default.
    The LLM layer can do smarter rewrites later.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    # Count em dashes (both — and the unicode character)
    em_dash_pattern = re.compile(r'—|--')
    matches = em_dash_pattern.findall(text)

    if matches:
        # Replace em dashes with commas (safe default)
        # Add spaces around the comma if not already present
        text = re.sub(r'\s*—\s*', ', ', text)
        text = re.sub(r'\s*--\s*', ', ', text)

        changes.append({
            'pattern': 14,
            'name': 'Em dash replaced',
            'detail': f'Replaced {len(matches)} em dash(es) with commas',
        })

    return text, changes


def fix_curly_quotes(text, changes):
    """
    Pattern 19: Replace curly quotes with straight quotes.

    ChatGPT uses curly/smart quotes ("...") instead of straight
    quotes ("..."). This is a dead giveaway of AI text.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    count = 0

    # Replace curly double quotes
    for curly in ['\u201c', '\u201d']:  # " and "
        if curly in text:
            count += text.count(curly)
            text = text.replace(curly, '"')

    # Replace curly single quotes / apostrophes
    for curly in ['\u2018', '\u2019']:  # ' and '
        if curly in text:
            count += text.count(curly)
            text = text.replace(curly, "'")

    if count:
        changes.append({
            'pattern': 19,
            'name': 'Curly quotes fixed',
            'detail': f'Replaced {count} curly quote(s) with straight quotes',
        })

    return text, changes


def fix_chatbot_artifacts(text, changes):
    """
    Pattern 20 + 22: Remove chatbot communication artifacts.

    AI text often includes leftover chatbot phrases like
    "I hope this helps!" or "Great question!" that make no sense
    in a finished document.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    chatbot_patterns = [
        r"(?:Great|Excellent|Fantastic|Wonderful|Good) question[.!]*\s*",
        r"(?:I hope this helps|Hope this helps)[.!]*\s*",
        r"(?:Let me know if you[' ](?:d like|need|want|have))[^.!]*[.!]*\s*",
        r"(?:Feel free to (?:ask|reach out|let me know))[^.!]*[.!]*\s*",
        r"(?:You'?re absolutely right)[.!]*\s*",
        r"(?:That'?s (?:a great|an excellent|a fantastic) (?:point|question|observation))[.!]*\s*",
        r"(?:Of course|Certainly|Absolutely)[.!]+\s*",
        r"(?:Here is|Here'?s) (?:a |an )?(?:overview|summary|breakdown|explanation)[^.]*[.:]\s*",
        r"(?:I'?d be happy to|I'?m happy to)[^.!]*[.!]*\s*",
    ]

    removed = 0
    for pattern_str in chatbot_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            removed += len(matches)
            text = pattern.sub('', text)

    if removed:
        # Clean up leftover whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'  +', ' ', text)
        text = text.strip()

        changes.append({
            'pattern': 20,
            'name': 'Chatbot artifacts removed',
            'detail': f'Removed {removed} chatbot phrase(s)',
        })

    return text, changes


def fix_signposting(text, changes):
    """
    Pattern 28: Remove signposting and announcement phrases.

    AI text announces what it's about to do instead of just doing it.
    "Let's dive into..." adds nothing. Just start with the content.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    removed = 0
    for pattern_str in SIGNPOSTING_PHRASES:
        pattern = re.compile(pattern_str + r'[.!:,]*\s*', re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            removed += len(matches)
            text = pattern.sub('', text)

    if removed:
        text = re.sub(r'  +', ' ', text)
        text = text.strip()
        changes.append({
            'pattern': 28,
            'name': 'Signposting removed',
            'detail': f'Removed {removed} signposting phrase(s)',
        })

    return text, changes


def fix_authority_tropes(text, changes):
    """
    Pattern 27: Remove persuasive authority tropes.

    AI text uses phrases like "At its core..." or "The real question is..."
    to pretend it's cutting through noise to deeper truth. Usually the
    sentence that follows is just an ordinary point.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    removed = 0
    for pattern_str in AUTHORITY_TROPES:
        pattern = re.compile(pattern_str + r'[,:]?\s*', re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            removed += len(matches)
            text = pattern.sub('', text)

    if removed:
        text = re.sub(r'  +', ' ', text)
        # Fix sentences that now start with lowercase
        text = re.sub(r'(?<=\. )[a-z]', lambda m: m.group().upper(), text)
        text = text.strip()
        changes.append({
            'pattern': 27,
            'name': 'Authority tropes removed',
            'detail': f'Removed {removed} persuasive framing phrase(s)',
        })

    return text, changes


def flag_promotional_words(text, changes):
    """
    Pattern 4: Flag promotional and advertisement-like language.

    These words are hard to auto-replace because the replacement
    depends on context. We flag them so the user can review.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list) — text unchanged, flags added
    """
    flagged = []
    for word in PROMOTIONAL_WORDS:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            flagged.append(f'"{word}" ({len(matches)}x)')

    if flagged:
        changes.append({
            'pattern': 4,
            'name': 'Promotional language flagged (review these)',
            'detail': ', '.join(flagged),
        })

    # Text is NOT modified here — just flagged for review
    return text, changes


def flag_significance_inflation(text, changes):
    """
    Pattern 1: Flag significance inflation phrases.

    These phrases puff up importance artificially. They are too
    context-dependent to auto-replace, so we flag them.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list) — text unchanged, flags added
    """
    flagged = []
    for pattern_str in SIGNIFICANCE_PHRASES:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            flagged.append(f'"{matches[0]}" ({len(matches)}x)')

    if flagged:
        changes.append({
            'pattern': 1,
            'name': 'Significance inflation flagged (review these)',
            'detail': ', '.join(flagged),
        })

    return text, changes


def fix_excessive_hedging(text, changes):
    """
    Pattern 24: Simplify excessive hedging.

    AI text over-qualifies statements by stacking hedge words:
    "could potentially possibly" → "may"

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    hedging_patterns = [
        # "could potentially" → "may"
        (r'\bcould potentially\b', 'may'),
        # "it could be argued that" → remove
        (r'\bit could be argued that\s*', ''),
        # "it might be said that" → remove
        (r'\bit might be said that\s*', ''),
        # "could potentially possibly" → "may"
        (r'\bcould potentially possibly\b', 'may'),
        # "it is possible that" → "possibly" or remove
        (r'\bit is possible that\s*', ''),
        # "might potentially" → "might"
        (r'\bmight potentially\b', 'might'),
    ]

    count = 0
    for pattern_str, replacement in hedging_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            count += len(matches)
            text = pattern.sub(replacement, text)

    if count:
        text = re.sub(r'  +', ' ', text)
        changes.append({
            'pattern': 24,
            'name': 'Excessive hedging simplified',
            'detail': f'Simplified {count} hedging phrase(s)',
        })

    return text, changes


def fix_bold_and_emojis(text, changes):
    """
    Pattern 15 + 18: Remove markdown bold formatting and emojis.

    AI text overuses **bold** emphasis and decorates with emojis.
    Both are strong AI tells in body text.

    Args:
        text (str): The current text being processed
        changes (list): Running list of changes made so far

    Returns:
        tuple: (modified_text, changes_list)
    """
    count = 0

    # Remove markdown bold markers ** but keep the text inside
    bold_pattern = re.compile(r'\*\*(.+?)\*\*')
    bold_matches = bold_pattern.findall(text)
    if bold_matches:
        count += len(bold_matches)
        text = bold_pattern.sub(r'\1', text)

    # Remove common emojis (a broad pattern for emoji unicode ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\u2600-\u26FF"          # misc symbols
        "\u2700-\u27BF"          # dingbats
        "\u23E9-\u23F3"          # media symbols
        "\u2702-\u27B0"          # more dingbats
        "\uFE00-\uFE0F"         # variation selectors
        "\u200D"                 # zero width joiner
        "]+",
        flags=re.UNICODE
    )
    emoji_matches = emoji_pattern.findall(text)
    if emoji_matches:
        count += len(emoji_matches)
        text = emoji_pattern.sub('', text)

    if count:
        text = re.sub(r'  +', ' ', text)
        changes.append({
            'pattern': 15,
            'name': 'Bold/emoji removed',
            'detail': f'Removed {count} bold marker(s) or emoji(s)',
        })

    return text, changes


# ─── THE MAIN PIPELINE ──────────────────────────────────────────────────────


def humanize_rule_based(text):
    """
    Run all rule-based pattern fixes on the input text.

    This is the main entry point for Layer 1 of the hybrid approach.
    It runs each fix function in sequence, collecting all changes.

    The order matters:
    1. Remove chatbot artifacts first (they're noise)
    2. Remove signposting and authority tropes
    3. Fix filler phrases and hedging
    4. Fix vocabulary and copula avoidance
    5. Fix style issues (em dashes, curly quotes, bold/emoji)
    6. Flag things that need manual review (promotional, significance)

    Args:
        text (str): The AI-generated text to humanize

    Returns:
        dict: {
            'text': str,        # The humanized text
            'changes': list,    # List of dicts describing each change
            'stats': dict,      # Summary statistics
        }
    """
    # This list will collect all changes made by every function
    changes = []

    # Store original for comparison
    original_text = text
    original_word_count = len(text.split())

    # ── Run the pipeline ──
    # Each function modifies text and appends to changes list

    text, changes = fix_chatbot_artifacts(text, changes)      # Pattern 20, 22
    text, changes = fix_signposting(text, changes)            # Pattern 28
    text, changes = fix_authority_tropes(text, changes)       # Pattern 27
    text, changes = fix_filler_phrases(text, changes)         # Pattern 23
    text, changes = fix_excessive_hedging(text, changes)      # Pattern 24
    text, changes = fix_ai_vocabulary(text, changes)          # Pattern 7
    text, changes = fix_copula_avoidance(text, changes)       # Pattern 8
    text, changes = fix_em_dashes(text, changes)              # Pattern 14
    text, changes = fix_curly_quotes(text, changes)           # Pattern 19
    text, changes = fix_bold_and_emojis(text, changes)        # Pattern 15, 18
    text, changes = flag_promotional_words(text, changes)     # Pattern 4
    text, changes = flag_significance_inflation(text, changes)  # Pattern 1

    # ── Compute stats ──
    final_word_count = len(text.split())

    stats = {
        'original_words': original_word_count,
        'final_words': final_word_count,
        'words_removed': original_word_count - final_word_count,
        'patterns_found': len(changes),
    }

    return {
        'text': text.strip(),
        'changes': changes,
        'stats': stats,
    }