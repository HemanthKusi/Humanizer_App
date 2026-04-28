"""
readability.py — Flesch Reading Ease calculator

Calculates how easy text is to read using the standard Flesch formula.
Used to show before/after readability scores so users can see
their text got simpler and clearer after humanizing.

Formula:
    Score = 206.835 - (1.015 × ASL) - (84.6 × ASW)
    ASL = average sentence length (words per sentence)
    ASW = average syllables per word

Score ranges:
    90-100  Very easy (5th grade)
    60-70   Standard (8th grade, newspapers)
    30-50   Difficult (college)
    0-30    Very difficult (academic)
"""

import re


def count_syllables(word):
    """
    Count the number of syllables in a single English word.

    Uses a vowel-group heuristic: counts clusters of consecutive
    vowels as one syllable each, then adjusts for common patterns
    like silent 'e' at the end.

    Not perfect (English is messy), but accurate enough for
    readability scoring where we average over hundreds of words.

    @param word: A single word (string)
    @return: Integer syllable count (minimum 1)
    """
    word = word.lower().strip()

    # Remove non-alpha characters
    word = re.sub(r'[^a-z]', '', word)

    if not word:
        return 1

    # Special short words that trip up the algorithm
    if len(word) <= 2:
        return 1

    # Count vowel groups (consecutive vowels = 1 syllable)
    vowel_groups = re.findall(r'[aeiouy]+', word)
    count = len(vowel_groups)

    # Silent 'e' at end: subtract 1 if word ends in 'e'
    # but NOT if the word ends in 'le' (like "table", "simple")
    if word.endswith('e') and not word.endswith('le'):
        count -= 1

    # Words ending in 'ed' where 'ed' is not its own syllable
    # (like "walked" = 1 syl, not "walk-ed")
    # Exception: words ending in 'ted' or 'ded' where it IS a syllable
    if word.endswith('ed') and len(word) > 3:
        if not word.endswith('ted') and not word.endswith('ded'):
            count -= 1

    # Every word has at least 1 syllable
    return max(count, 1)


def split_sentences(text):
    """
    Split text into sentences.

    Uses punctuation (.!?) as delimiters. Not perfect for edge cases
    like "Dr. Smith" or "U.S.A." but good enough for scoring.

    @param text: Full text string
    @return: List of sentence strings (non-empty)
    """
    # Split on . ! ? followed by space or end of string
    sentences = re.split(r'[.!?]+(?:\s|$)', text)

    # Remove empty strings
    return [s.strip() for s in sentences if s.strip()]


def split_words(text):
    """
    Split text into words.

    Strips punctuation and returns only actual words.

    @param text: Full text string
    @return: List of word strings
    """
    # Match sequences of letters/apostrophes (keeps contractions like "don't")
    return re.findall(r"[a-zA-Z']+", text)


def flesch_reading_ease(text):
    """
    Calculate the Flesch Reading Ease score for a piece of text.

    Returns both the numeric score and a human-readable label.

    @param text: The text to analyze (string)
    @return: Dictionary with:
        - score (float): The Flesch score, clamped to 0-100
        - label (string): Human-readable difficulty level
        - sentences (int): Number of sentences found
        - words (int): Number of words found
        - avg_sentence_length (float): Words per sentence
        - avg_syllables_per_word (float): Syllables per word
    """
    sentences = split_sentences(text)
    words = split_words(text)

    # Need at least 1 sentence and 1 word to calculate
    if len(sentences) == 0 or len(words) == 0:
        return {
            'score': 0,
            'sentences': 0,
            'words': 0,
            'avg_sentence_length': 0,
            'avg_syllables_per_word': 0,
        }

    # Average sentence length (ASL)
    asl = len(words) / len(sentences)

    # Average syllables per word (ASW)
    total_syllables = sum(count_syllables(w) for w in words)
    asw = total_syllables / len(words)

    # The Flesch formula
    score = 206.835 - (1.015 * asl) - (84.6 * asw)

    # Clamp between 0 and 100
    score = max(0, min(100, score))

    return {
        'score': round(score, 1),
        'sentences': len(sentences),
        'words': len(words),
        'avg_sentence_length': round(asl, 1),
        'avg_syllables_per_word': round(asw, 2),
    }