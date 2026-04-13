"""
core/llm_engine.py
------------------
LLM-powered humanizer engine (Layer 2 of the hybrid approach).

This module sends original text to an LLM (GPT-4o mini by default)
with a carefully crafted system prompt that instructs it to rewrite
the text so it sounds like a real human wrote it.

The module is designed to be MODULAR — switching from OpenAI to
Anthropic (Claude) requires changing just the provider config and
the API call function. The system prompt stays the same.

Usage:
    from core.llm_engine import humanize_with_llm

    result = humanize_with_llm("User text here...")
    print(result['text'])    # The LLM-rewritten text

Environment variables needed in .env:
    OPENAI_API_KEY=sk-...
    LLM_PROVIDER=openai          (or "anthropic" later)
    LLM_MODEL=gpt-4o-mini        (or "claude-sonnet-4-20250514" later)
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ─── CONFIGURATION ──────────────────────────────────────────────────────────
#
# These read from your .env file. To switch providers later,
# just change the values in .env — no code changes needed.

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai')
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o-mini')


# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────
#
# This is the most important part of the entire project.
#
# This prompt tells the LLM exactly HOW to rewrite text so it sounds
# human. It's condensed from SKILL.md to save tokens (every token
# costs money), but covers the same core patterns.
#
# Key principles baked into this prompt:
# 1. Vary sentence rhythm (short + long, not uniform)
# 2. Use simple words over fancy ones
# 3. Have opinions and acknowledge complexity
# 4. Use first person when appropriate
# 5. Be specific, not vague
# 6. Let some imperfection in — perfect structure feels algorithmic

SYSTEM_PROMPT = """You are rewriting text so it passes AI detection tools. AI detectors measure two things:

1. PERPLEXITY — how predictable each word choice is. AI picks the "obvious" next word. Humans don't. You must use LESS PREDICTABLE word choices. Not wrong words. Just not the statistically obvious ones.

2. BURSTINESS — how much sentence length varies. AI writes uniform sentences. Humans write one 4-word sentence, then a 30-word one, then a 12-word one. You must dramatically vary sentence length.

REWRITING RULES:

SENTENCE STRUCTURE:
- Mix very short sentences (3-6 words) with long winding ones
- Start some sentences with "And" or "But" or "So"
- Use sentence fragments occasionally. Like this.
- Break a long thought across two sentences where AI would use one
- Throw in a one-word sentence if it fits. Seriously.

WORD CHOICE:
- Use contractions always: "don't" not "do not", "it's" not "it is", "won't" not "will not"
- Pick the less obvious synonym. Not "important" — say "big deal" or "worth paying attention to"
- Use casual phrases: "kind of", "pretty much", "honestly", "the thing is"
- Sprinkle in filler that humans use: "I mean", "look", "right?"
- Avoid these AI-favorite words entirely: crucial, pivotal, landscape, tapestry, delve, foster, leverage, utilize, comprehensive, robust, nuanced, innovative, streamline, paramount, multifaceted, transformative, groundbreaking, testament

PARAGRAPH STRUCTURE:
- Some paragraphs should be one sentence
- Others can be 4-5 sentences
- Don't follow a pattern. Make it uneven.

VOICE:
- Write in first person when it fits. Use "I think", "I'd argue", "from what I've seen"
- Have actual opinions. Don't hedge everything with "some might say"
- Acknowledge when something is complicated or when you're unsure
- Be slightly informal. Not sloppy, but relaxed. Like you're explaining to a smart friend.

THINGS TO ABSOLUTELY AVOID:
- Don't start with a summary sentence that previews the whole piece
- Don't end with a neat conclusion that wraps everything up
- Don't use "In conclusion", "To summarize", "Overall"
- Don't use transition words at the start of every paragraph: "Moreover", "Furthermore", "Additionally", "However"
- Don't use the phrase "It's worth noting" or "It's important to"
- Don't use semicolons (humans rarely do in casual writing)
- No bullet points or numbered lists
- No markdown bold **like this**
- Straight quotes "like this" not curly quotes
- No emojis

CRITICAL INSTRUCTION: Return ONLY the rewritten text. No preamble. No "Here's the rewritten version:". No commentary after. Just the text."""


# ─── API CALL FUNCTIONS ─────────────────────────────────────────────────────


def call_openai(text):
    """
    Send text to OpenAI's API for rewriting.

    Creates an OpenAI client, sends the system prompt + user text,
    and returns the rewritten text.

    Args:
        text (str): The text to rewrite

    Returns:
        str: The LLM-rewritten text

    Raises:
        Exception: If the API call fails for any reason
    """
    # Create the OpenAI client
    # It automatically reads OPENAI_API_KEY from environment
    client = OpenAI()

    # Make the API call
    # "messages" is a list of the conversation:
    #   - system message: tells the LLM its role and rules
    #   - user message: the actual text to rewrite
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"Rewrite this text so it passes AI detection. Make it sound like a real person talking, not a polished article:\n\n{text}",
            },
        ],
        temperature=1.1,    # Higher = less predictable word choices
        max_tokens=4096,
    )

    # Extract the text from the response object
    # The response structure is: response.choices[0].message.content
    return response.choices[0].message.content.strip()


def call_anthropic(text):
    """
    Send text to Anthropic's Claude API for rewriting.

    This function is ready for when you switch to Claude later.
    Just change LLM_PROVIDER to "anthropic" in your .env file.

    Args:
        text (str): The text to rewrite

    Returns:
        str: The LLM-rewritten text

    Raises:
        Exception: If the API call fails for any reason
    """
    import anthropic

    # Create the Anthropic client
    # It automatically reads ANTHROPIC_API_KEY from environment
    client = anthropic.Anthropic()

    # Make the API call
    # Claude uses a slightly different format than OpenAI
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Rewrite this text so it passes AI detection. Make it sound like a real person talking, not a polished article:\n\n{text}",
            },
        ],
    )

    # Claude returns content as a list of blocks
    # For text responses, it's response.content[0].text
    return response.content[0].text.strip()


# ─── MAIN ENTRY POINT ───────────────────────────────────────────────────────


def humanize_with_llm(text):
    """
    Send text to the configured LLM for deep rewriting.

    This is the main entry point for Layer 2 of the hybrid approach.
    It reads LLM_PROVIDER from your .env file and calls the
    appropriate API function.

    Args:
        text (str): Text to rewrite

    Returns:
        dict: {
            'text': str,        # The LLM-rewritten text
            'provider': str,    # Which LLM was used ('openai' or 'anthropic')
            'model': str,       # Which model was used ('gpt-4o-mini', etc.)
        }

    Raises:
        ValueError: If LLM_PROVIDER is not recognized
        Exception: If the API call fails
    """
    # Route to the correct provider
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