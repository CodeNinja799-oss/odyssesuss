"""Day 3 - context: keeping a long run inside a finite window.

A transcript only grows: every tool result is appended and nothing is removed,
so a long task eventually costs more to send than to finish. Compaction trades
old detail for a summary, through the `before_turn` socket day 1 left open.

Design rules embodied here:
  * Recent turns stay verbatim. The model needs the last few exchanges exactly
    as they happened; only the distant past is worth paraphrasing.
  * Compaction is a model call like any other, so what survives is decided by
    an instruction you can read and edit, not by a heuristic buried in code.
  * Never strand a tool result. A functionResponse whose call was summarised
    away is invalid to the provider, so orphans are dropped, not kept.
"""

from . import provider

CHARS_PER_TOKEN = 4    # crude but stable: good enough to decide *when* to compact
KEEP_RECENT = 6        # messages left untouched at the end of the transcript
CLIP = 1000            # characters kept per message when rendering the old part

SYSTEM = ("You compress agent transcripts. Preserve: the original task, every "
          "file created or edited and its purpose, key decisions, unresolved "
          "errors, and what remains to be done. Be dense and factual.")


def estimate_tokens(messages: list) -> int:
    """Approximate the token cost of a message list.

    Crude on purpose: this decides when to compact, never what to bill, and a
    character count needs no tokenizer and no network call.
    """
    return sum(len(str(message)) for message in messages) // CHARS_PER_TOKEN


def compact(model: str, messages: list, budget_tokens: int) -> list:
    """Return `messages` shortened to fit `budget_tokens`, or unchanged.

    The tail stays verbatim; everything older becomes one summary message.
    Called from the before_turn socket, so it runs between turns, never in the
    middle of a tool call.
    """
    if len(messages) <= KEEP_RECENT + 1 or estimate_tokens(messages) <= budget_tokens:
        return messages
    old, recent = messages[:-KEEP_RECENT], messages[-KEEP_RECENT:]
    # A tool result whose originating call now lives inside the summary has
    # nothing to answer: the provider rejects it, so drop it from the front.
    while recent and recent[0]["role"] == "tool":
        recent = recent[1:]
    summary = provider.complete(model, SYSTEM, [{"role": "user", "text": _render(old)}])["text"]
    return [{"role": "user", "text": f"[Conversation so far, compacted]\n{summary}"}] + recent


def _render(messages: list) -> str:
    """Flatten messages into a plain transcript for the summariser to read."""
    lines = []
    for message in messages:
        label = message["role"] + (f" ({message['name']})" if message.get("name") else "")
        body = (message.get("text") or "")[:CLIP]
        called = ", ".join(call["name"] for call in message.get("tool_calls") or [])
        lines.append(f"{label}: {body}" + (f" [called: {called}]" if called else ""))
    return "\n".join(lines)
