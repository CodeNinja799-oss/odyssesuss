"""Day 1 - the agent loop: call the model, run what it asks for, call again.

This is the whole of "agency": no planner, no state machine, just a loop that
keeps calling the model while the model keeps asking for tools.

Design rules embodied here:
  * The transcript is the state. Everything the loop learns it appends to
    `messages`; nothing is remembered anywhere else.
  * A tool failure is data, not a crash. Errors come back as tool results so
    the model can read them and try something else.
  * Policy and observation are injected, not embedded: `before_tool` decides
    what may run, `on_event` is the single window a UI gets.
"""

from . import provider


def run_loop(model: str, system: str, messages: list, tools: dict, on_event,
             before_tool, max_turns: int = 80, before_turn=None) -> str:
    """Drive the model to a final answer and return that answer's text.

    Args:
        model, system: passed straight to the provider.
        messages: the transcript, mutated in place - the caller keeps the record.
        tools: name -> Tool, where a Tool has `.spec` ({"schema": ...}) and
            `.run(**kwargs)`.
        on_event: on_event(kind, payload) for "assistant", "tool_start", "tool_end".
        before_tool: before_tool(call) -> None to allow, or a reason to block.
        max_turns: how many model calls before the loop insists on an answer.
        before_turn: optional hook returning a replacement message list, used
            before each model call. Unused on day 1; day 3 hangs compaction here.
    """
    specs = [tool.spec for tool in tools.values()]
    for _ in range(max_turns):
        if before_turn:
            # Replaces the list in place: the caller's reference stays valid.
            messages[:] = before_turn(messages)
        reply = provider.complete(model, system, messages, specs)
        messages.append({"role": "assistant", "text": reply["text"],
                         "tool_calls": reply["tool_calls"]})
        on_event("assistant", reply)
        if not reply["tool_calls"]:
            return reply["text"]
        for call in reply["tool_calls"]:
            on_event("tool_start", call)
            result = _execute(tools, call, before_tool)
            messages.append({"role": "tool", "name": call["name"], "text": str(result)})
            on_event("tool_end", {"call": call, "result": result})

    # Out of turns: strip the tools away so the next call can only be prose.
    messages.append({"role": "user", "text": "Turn limit reached; wrap up now."})
    final = provider.complete(model, system, messages, None)
    messages.append({"role": "assistant", "text": final["text"], "tool_calls": []})
    return final["text"]


def _execute(tools: dict, call: dict, before_tool) -> str:
    """Run one tool call, converting every failure into a readable result.

    The gate is consulted before dispatch, so a blocked call never reaches the
    tool. Nothing raised in here escapes: the loop must survive any tool.
    """
    reason = before_tool(call)
    if reason:
        return f"BLOCKED: {reason}"
    tool = tools.get(call["name"])
    if tool is None:
        return f"ERROR: unknown tool {call['name']}"
    try:
        return tool.run(**call["args"])
    except Exception as error:
        return f"ERROR: {type(error).__name__}: {error}"
