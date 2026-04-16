"""
core/sanitizer.py
----------------
Input sanitization for user-provided text.

This module cleans text before it's processed by the humanizer
engines. It handles:
    - Invisible/zero-width characters
    - Unicode normalization
    - Repeated character flooding
    - HTML and script tags
    - Excessive whitespace
    - Control characters

Always call sanitize_input() on any user text BEFORE processing.
Frontend validation is not enough — attackers bypass frontends.
"""

import re
from better_profanity import profanity
import unicodedata


# Characters that are invisible or cause rendering issues
# Zero-width space, zero-width non-joiner, zero-width joiner, etc.
INVISIBLE_CHARS = [
    '\u200b',  # Zero-width space
    '\u200c',  # Zero-width non-joiner
    '\u200d',  # Zero-width joiner
    '\u2060',  # Word joiner
    '\ufeff',  # Zero-width no-break space (BOM)
    '\u00ad',  # Soft hyphen
    '\u180e',  # Mongolian vowel separator
]

# Pattern for HTML/script tags
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

# Pattern for script-like content (javascript:, data:, etc.)
DANGEROUS_URI_PATTERN = re.compile(
    r'(?:javascript|data|vbscript|file|about):', re.IGNORECASE
)

# Maximum consecutive identical characters allowed
# "aaaa" is fine. "aaaaaaaaaa" gets capped.
MAX_REPEATED_CHARS = 5


def remove_invisible_chars(text):
    """
    Remove zero-width and other invisible unicode characters.

    These characters can be used to:
        - Hide content inside seemingly normal text
        - Bypass word/character counters
        - Confuse text processing

    Args:
        text (str): The input text

    Returns:
        str: Text with invisible characters removed
    """
    for char in INVISIBLE_CHARS:
        text = text.replace(char, '')
    return text


def normalize_unicode(text):
    """
    Normalize unicode to NFKC form.

    This converts lookalike characters to their canonical form.
    For example:
        - Full-width characters (ｈｅｌｌｏ) → regular (hello)
        - Combined characters → single characters
        - Compatible forms are unified

    NFKC is stricter than NFC — it catches more attack variations.

    Args:
        text (str): The input text

    Returns:
        str: Unicode-normalized text
    """
    return unicodedata.normalize('NFKC', text)


def remove_control_chars(text):
    """
    Strip control characters except common whitespace (\\n, \\t, \\r).

    Control characters like NULL, bell, form feed have no place in
    user text and can cause processing issues.

    Args:
        text (str): The input text

    Returns:
        str: Text with control characters removed
    """
    # Keep printable chars + newline, tab, carriage return
    allowed = ('\n', '\t', '\r')
    return ''.join(
        c for c in text
        if c in allowed or not unicodedata.category(c).startswith('C')
    )


def cap_repeated_characters(text):
    """
    Cap consecutive identical characters at MAX_REPEATED_CHARS.

    Prevents flooding attacks like "aaaaaaa..." that could consume
    API tokens or crash processing.

    For example, with max=5:
        "aaaaaaaaa" → "aaaaa"
        "Hello!!!!" → "Hello!!!!!" (already under cap)
        "????????????" → "?????"

    Args:
        text (str): The input text

    Returns:
        str: Text with repeated runs capped
    """
    # Match any character repeated more than MAX_REPEATED_CHARS times
    # Backreference \1 matches the same character captured in group 1
    pattern = re.compile(r'(.)\1{' + str(MAX_REPEATED_CHARS) + r',}')
    return pattern.sub(lambda m: m.group(1) * MAX_REPEATED_CHARS, text)


def strip_html_tags(text):
    """
    Remove HTML and XML tags from text.

    We strip rather than escape because users are pasting writing,
    not markup. Any tags present are almost certainly junk or attacks.

    Args:
        text (str): The input text

    Returns:
        str: Text with HTML tags removed
    """
    return HTML_TAG_PATTERN.sub('', text)


def remove_dangerous_uris(text):
    """
    Remove dangerous URI schemes that could be injection attempts.

    javascript:, data:, vbscript: etc. don't belong in writing samples
    and are classic XSS vectors.

    Args:
        text (str): The input text

    Returns:
        str: Text with dangerous URI prefixes neutralized
    """
    return DANGEROUS_URI_PATTERN.sub('', text)


def collapse_whitespace(text):
    """
    Collapse excessive whitespace while preserving paragraph structure.

    Rules:
        - Multiple spaces → single space
        - Multiple newlines → max two (paragraph break)
        - Leading/trailing whitespace → removed

    Args:
        text (str): The input text

    Returns:
        str: Text with normalized whitespace
    """
    # Replace multiple spaces/tabs with one space
    text = re.sub(r'[ \t]+', ' ', text)

    # Replace 3+ newlines with 2 (preserves paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace from each line
    text = '\n'.join(line.strip() for line in text.split('\n'))

    # Strip overall
    return text.strip()

def filter_profanity(text):
    """
    Detect profane/18+ content and identify the specific words.

    Returns the flagged words so the frontend can highlight them.

    Args:
        text (str): The input text

    Returns:
        tuple: (cleaned_text, was_flagged, flagged_words)
            cleaned_text — original text (uncensored, for highlighting)
            was_flagged — True if any profanity was found
            flagged_words — list of the actual bad words found
    """
    profanity.load_censor_words()

    custom_words = [
        'nsfw', 'onlyfans', 'pornhub', 'xvideos', 'redtube',
        'hentai', 'camgirl', 'sexting', 'nudes',
    ]
    profanity.add_censor_words(custom_words)

    was_flagged = profanity.contains_profanity(text)

    # Find which specific words were flagged
    flagged_words = []
    if was_flagged:
        words = re.findall(r'\b\w+\b', text)
        for word in words:
            if profanity.contains_profanity(word):
                lower = word.lower()
                if lower not in flagged_words:
                    flagged_words.append(lower)

    return text, was_flagged, flagged_words


def sanitize_input(text):
    """
    Full sanitization pipeline for user-submitted text.

    Runs all cleaning steps in order:
        1. Unicode normalization
        2. Remove invisible characters
        3. Remove control characters
        4. Strip HTML tags
        5. Remove dangerous URIs
        6. Cap repeated characters
        7. Collapse whitespace
        8. Filter profanity

    Args:
        text (str): Raw user input

    Returns:
        dict: {
            'text': str,           # Cleaned, safe text
            'profanity_flagged': bool  # True if profanity was found
            'flagged_words': list,   # List of flagged words (if any)
        }

    Raises:
        ValueError: If text is None or not a string
    """
    if text is None:
        raise ValueError('Text cannot be None')
    if not isinstance(text, str):
        raise ValueError('Text must be a string')

    # Run the cleaning pipeline
    text = normalize_unicode(text)
    text = remove_invisible_chars(text)
    text = remove_control_chars(text)
    text = strip_html_tags(text)
    text = remove_dangerous_uris(text)
    text = cap_repeated_characters(text)
    text = collapse_whitespace(text)

    # Filter profanity (last step so it works on clean text)
    text, profanity_flagged, flagged_words = filter_profanity(text)

    return {
        'text': text,
        'profanity_flagged': profanity_flagged,
        'flagged_words': flagged_words,
    }