"""
core/llm_engine.py
------------------
LLM-powered writing quality engine (Layer 2 of the hybrid approach).

PURPOSE: Take AI-generated text and rewrite it into genuinely good
writing — concise, specific, opinionated, and readable.

This is NOT about fooling AI detectors. It's about producing writing
that a human editor would be proud of.

APPROACH: Single-pass rewrite with a detailed system prompt based on
the 29 patterns from SKILL.md (Wikipedia's "Signs of AI writing").

One strong pass with a good prompt produces better writing than
multiple passes that fight each other. The prompt does the heavy
lifting — it tells the model exactly what good writing looks like
and what to avoid.

Environment variables needed in .env:
    OPENAI_API_KEY=sk-...
    LLM_PROVIDER=openai
    LLM_MODEL=gpt-4o
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai')
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o')


# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────
#
# This prompt is the core of the entire product.
#
# It's built from SKILL.md's 29 patterns but restructured around
# a single goal: make the writing genuinely good, not just "less AI."
#
# The prompt is organized into:
#   1. What to CUT (the junk AI adds)
#   2. What to FIX (structural problems)
#   3. What to ADD (the soul that's missing)
#   4. Hard rules (absolute don'ts)
#
# We keep it detailed but not bloated. Every line earns its tokens.

SYSTEM_PROMPT = """You are a senior writing editor. Someone hands you an AI-generated draft. Your job: turn it into something a good writer would actually publish.

You're not polishing. You're rewriting. The draft is raw material, not a finished piece that needs tweaks.

## WHAT TO CUT

These are the dead giveaways of AI writing. Remove them completely:

FILLER PHRASES: "it is important to note that", "in order to", "due to the fact that", "at the end of the day", "a wide range of", "the vast majority of", "each and every", "when all is said and done". If a phrase can disappear without changing the meaning, it should.

SIGNIFICANCE INFLATION: Don't call things "pivotal", "transformative", "groundbreaking", "a testament to", "marking a pivotal moment", "setting the stage for" unless they literally changed history. Most things are just things.

PROMOTIONAL LANGUAGE: "breathtaking", "stunning", "world-class", "unparalleled", "nestled in the heart of", "rich tapestry". This is brochure writing. Cut it.

CHATBOT ARTIFACTS: "Great question!", "I hope this helps!", "Let me know if you'd like me to expand", "Certainly!", "Here's an overview of". These are conversation remnants. They don't belong in finished writing.

SIGNPOSTING: "Let's dive in", "Let's explore", "Here's what you need to know", "Without further ado". Just start with the content.

AUTHORITY TROPES: "At its core", "The real question is", "What really matters", "Fundamentally". These pretend to cut through noise but just add more of it.

KNOWLEDGE-CUTOFF HEDGING: "While specific details are limited", "Based on available information". Either know it or don't mention it.

GENERIC CONCLUSIONS: "The future looks bright", "Exciting times lie ahead", "This represents a step in the right direction". End with something specific or just stop.

## WHAT TO FIX

COPULA AVOIDANCE: AI writes "serves as", "functions as", "stands as", "boasts", "features" instead of "is" and "has". Use the simple word.

AI VOCABULARY: Replace these with normal words:
- "additionally/furthermore/moreover" → "also" or just start the sentence
- "utilize/leverage" → "use"
- "facilitate" → "help"
- "commence" → "start"
- "endeavor" → "try"
- "implement" → "set up" or "build"
- "optimize" → "improve"
- "streamline" → "simplify"
- "comprehensive" → just drop it, or "full" / "complete"
- "robust" → "solid" or "strong"

RULE OF THREE: AI groups things in threes compulsively. "Innovation, inspiration, and insights." Use whatever number is natural. Sometimes that's two. Sometimes four. Sometimes one.

SYNONYM CYCLING: AI avoids repeating words by cycling synonyms: "the protagonist... the main character... the central figure... the hero." If "protagonist" is the clearest word, use it every time.

FALSE RANGES: "From X to Y" where X and Y aren't on a meaningful scale. "From beginners to experts" is fine. "From the Big Bang to dark matter" is nonsense.

NEGATIVE PARALLELISMS: "It's not just X, it's Y" or "It's not about A, it's about B." Just state Y or B directly.

EM DASHES: AI overuses em dashes for punchy effect. Replace most with commas or periods. One em dash per piece is fine. Five is AI writing.

## WHAT TO ADD

This is the hard part. Clean writing without soul is still obviously AI.

VARIED RHYTHM: Mix short sentences with long ones. Real writing has texture. Some thoughts take three words. Others need thirty because the idea is complex and you're working through it as you write.

OPINIONS: Don't just report. React. "I think this matters because..." or "Honestly, this part is overhyped" or "The interesting bit isn't X, it's Y." A real writer has a take.

SPECIFICITY: Replace vague claims with concrete ones. Not "many people" — how many? Not "experts say" — who? Not "significant impact" — what specifically happened? If the original doesn't have specifics, either find them or honestly say the details aren't clear.

FIRST PERSON: Use "I" when it fits. "I keep coming back to this" or "Here's what bugs me about this" signals a thinking person behind the words. It's not unprofessional. It's honest.

UNCERTAINTY: Real writers acknowledge when something is complicated or when they don't have the full picture. "I'm not entirely sure about this, but..." is more trustworthy than false confidence.

IMPERFECTION: A tangent. An aside in parentheses. A thought that doesn't quite land perfectly. Perfect parallel structure in every paragraph is a machine tell. Let some human mess through.

## HARD RULES

- Use contractions: "don't" not "do not", "it's" not "it is"
- Straight quotes "like this" not curly quotes
- No **bold** formatting
- No emoji
- No bullet-point lists with bold headers in the output
- Write in paragraphs, not lists (unless a list genuinely makes sense)
- Don't start more than one paragraph with the same word
- Don't use semicolons in casual or general writing
- Never write "In conclusion" or "To summarize" or "Overall"

## OUTPUT

Return ONLY the rewritten text. No preamble like "Here's the rewritten version:". No commentary. No explanation of changes. Just the text, ready to publish."""


# ─── API CALL FUNCTIONS ─────────────────────────────────────────────────────


def call_openai(text):
    """
    Send text to OpenAI's API for quality rewriting.

    Uses a single pass with the detailed system prompt.
    frequency_penalty and presence_penalty encourage varied
    word choices and reduce repetition.

    Args:
        text (str): The original AI-generated text to rewrite

    Returns:
        str: The rewritten text
    """
    client = OpenAI()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        temperature=0.95,       # Creative but not chaotic
        max_tokens=4096,
        frequency_penalty=0.4,  # Discourage repeating the same words
        presence_penalty=0.3,   # Encourage covering new ground
    )

    return response.choices[0].message.content.strip()


def call_anthropic(text):
    """
    Send text to Anthropic's Claude API for quality rewriting.
    Ready for when you switch providers.

    Args:
        text (str): The original AI-generated text to rewrite

    Returns:
        str: The rewritten text
    """
    import anthropic

    client = anthropic.Anthropic()

    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": text,
            },
        ],
    )

    return response.content[0].text.strip()


# ─── MAIN ENTRY POINT ───────────────────────────────────────────────────────


def humanize_with_llm(text):
    """
    Rewrite AI-generated text into quality human writing.

    Single-pass approach: one strong prompt through a capable model
    produces better results than multiple weaker passes.

    The system prompt handles all 29 SKILL.md patterns plus
    the "soul" additions (voice, rhythm, opinions, specificity).

    Args:
        text (str): The original AI-generated text

    Returns:
        dict: {
            'text': str,        # The rewritten text
            'provider': str,    # Which LLM provider was used
            'model': str,       # Which model was used
        }

    Raises:
        ValueError: If LLM_PROVIDER in .env is not recognized
        Exception: If the API call fails
    """
    if LLM_PROVIDER == 'openai':
        rewritten = call_openai(text)
    elif LLM_PROVIDER == 'anthropic':
        rewritten = call_anthropic(text)
    else:
        raise ValueError(
            f'Unknown LLM provider: "{LLM_PROVIDER}". '
            f'Set LLM_PROVIDER in .env to "openai" or "anthropic".'
        )

    return {
        'text': rewritten,
        'provider': LLM_PROVIDER,
        'model': LLM_MODEL,
    }