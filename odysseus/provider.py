"""Day 1 - the provider seam: the one file that speaks Gemini's wire format.

Above it, a small neutral message format; below it, HTTP and JSON. Swap
vendors and only this file is rewritten.

Design rules embodied here:
  * Neutral in, neutral out - no wire detail leaks up, no harness type leaks down.
  * Transport trouble is the provider's problem: rate limits and flaky sockets
    are retried here so the loop above never thinks about them.
  * Thought signatures round-trip verbatim - stored, echoed, never inspected.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-pro-preview"


def api_key() -> str:
    """Return the Gemini API key from the environment.

    ODYSSEUS_API_KEY is read first so a workshop key can shadow a personal one.
    """
    key = os.environ.get("ODYSSEUS_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("No API key. Set ODYSSEUS_API_KEY or GEMINI_API_KEY "
                           "(run: source odysseus-key.sh).")
    return key


def complete(model: str, system: str, messages: list, tools: list = None) -> dict:
    """Send one request to the model and return its reply.

    `tools` is a list of tool specs, each a dict with a "schema" key, or None.
    Returns {"text", "tool_calls": [{"name", "args", "signature"}], "usage"}.
    """
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _to_wire(messages),
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 65536},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [t["schema"] for t in tools]}]
    data = _post(f"{API_ROOT}/{model}:generateContent", body)

    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    # Parts flagged "thought" are private reasoning: never shown, never stored.
    text = "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))
    calls = [{"name": p["functionCall"].get("name"),
              "args": p["functionCall"].get("args") or {},
              "signature": p.get("thoughtSignature")}
             for p in parts if "functionCall" in p]
    usage = data.get("usageMetadata") or {}
    return {"text": text, "tool_calls": calls,
            "usage": {"input": usage.get("promptTokenCount", 0),
                      "output": usage.get("candidatesTokenCount", 0)}}


def _to_wire(messages: list) -> list:
    """Translate neutral messages into Gemini `contents`.

    The neutral format has exactly three shapes:
        {"role": "user", "text"}
        {"role": "assistant", "text", "tool_calls"}
        {"role": "tool", "name", "text"}
    Gemini has two roles, so a tool result returns as a user functionResponse.
    """
    wire = []
    for message in messages:
        role = message["role"]
        if role == "user":
            wire.append({"role": "user", "parts": [{"text": message["text"]}]})
        elif role == "assistant":
            parts = [{"text": message["text"]}] if message.get("text") else []
            for call in message.get("tool_calls") or []:
                part = {"functionCall": {"name": call["name"], "args": call["args"]}}
                # Opaque proof the call is the model's own: Gemini 3 rejects the
                # replayed turn without it, so it goes back exactly as it arrived.
                if call.get("signature"):
                    part["thoughtSignature"] = call["signature"]
                parts.append(part)
            wire.append({"role": "model", "parts": parts})
        elif role == "tool":
            wire.append({"role": "user", "parts": [{"functionResponse": {
                "name": message["name"], "response": {"result": message["text"]}}}]})
    return wire


def _post(url: str, body: dict, retries: int = 5) -> dict:
    """POST JSON to `url`, retrying transient failures with exponential backoff.

    429 and the 5xx family mean "ask again later", so we sleep and do. Any other
    status is a flaw in our own request, raised at once with the server's reason.
    """
    payload = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key()}
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, payload, headers, method="POST")
            with urllib.request.urlopen(request, timeout=600) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            detail = error.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"Gemini HTTP {error.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == retries - 1:
                raise RuntimeError(f"Gemini unreachable: {error}") from None
            time.sleep(2 ** attempt * 2)
    raise RuntimeError("Gemini request failed after all retries")
