"""Local Llama tool-calling loop using Ollama's HTTP API."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS


def ollama_chat(messages):
    declarations = [{"type": "function", "function": {
        key: value for key, value in tool.items() if key != "type"
    }} for tool in TOOL_DECLARATIONS]
    payload = {"model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
               "messages": messages, "tools": declarations, "stream": False,
               "options": {"temperature": 0, "num_ctx": 8192}}
    request = Request("http://127.0.0.1:11434/api/chat",
                      data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=180) as response:
            return json.load(response)["message"]
    except HTTPError as exc:
        raise RuntimeError("Ollama could not run the model. Check that llama3.1:8b is downloaded.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Local Llama is unavailable or timed out. Start Ollama with 'ollama serve'.") from exc


def run_llama(user_message, previous_state=None, verbose=False):
    from .agent import MAX_STEPS, SYSTEM_PROMPT
    history = []
    if isinstance(previous_state, dict) and previous_state.get("provider") == "ollama":
        history = list(previous_state.get("messages", []))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    messages.append({"role": "user", "content": user_message})
    for step in range(MAX_STEPS + 1):
        reply = ollama_chat(messages)
        calls = reply.get("tool_calls") or []
        if calls and step == MAX_STEPS:
            break
        messages.append(reply)
        if not calls:
            answer = reply.get("content") or "No answer was produced. Please rephrase."
            return answer, {"provider": "ollama", "messages": messages[1:]}
        for call in calls:
            function = call.get("function", {})
            name = function.get("name", "")
            arguments = function.get("arguments", {})
            try:
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if name not in TOOL_FUNCTIONS:
                    raise ValueError("Unknown inventory tool.")
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be an object.")
                result = TOOL_FUNCTIONS[name](**arguments)
            except (ValueError, TypeError) as exc:
                result = {"error": str(exc)}
            if verbose:
                print(f"{name}: {result}")
            messages.append({"role": "tool", "tool_name": name,
                             "content": json.dumps(result)})
    return "The local model needed too many steps. Please try a simpler question.", previous_state
