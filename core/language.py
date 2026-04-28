"""
core/language.py
----------------
Detects the language of input text using Google's langdetect library.

Used to:
1. Block non-English text in Quick Fix mode (rule-based is English-only)
2. Tell the LLM what language to rewrite in during Deep Rewrite mode
3. Show the detected language in the stats bar

The detector works by analyzing character patterns and common word
frequencies. It supports 50+ languages out of the box.
"""

from langdetect import detect, detect_langs, LangDetectException


# Map language codes to human-readable names
# These are the most common languages users are likely to paste.
# If a code isn't in this dict, we show the code itself (e.g., "tl" for Tagalog).
LANGUAGE_NAMES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'pt': 'Portuguese',
    'it': 'Italian',
    'nl': 'Dutch',
    'ru': 'Russian',
    'zh-cn': 'Chinese (Simplified)',
    'zh-tw': 'Chinese (Traditional)',
    'ja': 'Japanese',
    'ko': 'Korean',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'bn': 'Bengali',
    'tr': 'Turkish',
    'pl': 'Polish',
    'uk': 'Ukrainian',
    'sv': 'Swedish',
    'da': 'Danish',
    'no': 'Norwegian',
    'fi': 'Finnish',
    'cs': 'Czech',
    'ro': 'Romanian',
    'hu': 'Hungarian',
    'el': 'Greek',
    'he': 'Hebrew',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'id': 'Indonesian',
    'ms': 'Malay',
    'ta': 'Tamil',
    'te': 'Telugu',
    'ur': 'Urdu',
    'fa': 'Persian',
    'sw': 'Swahili',
}


def detect_language(text):
    """
    Detect the language of the given text.

    Returns the language code, human-readable name, and confidence score.
    For short text (under 20 words), defaults to English to avoid
    false detections — language detectors struggle with short input.

    @param text: The text to analyze (string)
    @return: Dictionary with:
        - code (str): ISO language code like 'en', 'fr', 'es'
        - name (str): Human-readable name like 'English', 'French'
        - confidence (float): How confident the detector is (0.0 to 1.0)
        - is_english (bool): True if the detected language is English
    """
    # Default result for edge cases
    default = {
        'code': 'en',
        'name': 'English',
        'confidence': 1.0,
        'is_english': True,
    }

    # Guard: empty or very short text defaults to English
    # Language detection is unreliable under ~20 words
    word_count = len(text.strip().split())
    if word_count < 10:
        return default

    try:
        # detect_langs() returns a list of possible languages
        # sorted by probability, e.g. [en:0.85, de:0.10, nl:0.05]
        results = detect_langs(text)

        if not results:
            return default

        # Take the top result
        top = results[0]
        code = top.lang
        confidence = round(top.prob, 2)

        # If confidence is low (under 70%), default to English
        # This prevents false positives on mixed-language text
        if confidence < 0.7:
            return default

        # Look up the human-readable name
        name = LANGUAGE_NAMES.get(code, code.upper())

        return {
            'code': code,
            'name': name,
            'confidence': confidence,
            'is_english': code == 'en',
        }

    except LangDetectException:
        # Library couldn't determine the language
        # (happens with very short or garbled input)
        return default