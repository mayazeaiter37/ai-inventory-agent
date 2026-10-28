import json
import os

from google import genai

from .tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

SYSTEM_PROMPT = """You are an inventory assistant for a small warehouse.

You help the user check and update stock by calling the tools available to you.

Rules:
- Always use a tool to answer questions about stock. Never guess or rely on memory.
- If a tool returns an error, explain the problem to the user in plain language.
- Before deleting an item entirely, make sure that is what the user meant.
- Always call calculate_cost for cost, price totals, or VAT calculations.
- Never invent a unit price. If it is missing, ask the user and use set_price.
- Prices are per unit before VAT. Pass 10 for 10% VAT, not 0.10.
- Show unit price, quantity, subtotal, VAT amount and final total for a cost question.
- A cost question is a quote: do not remove stock. Mention insufficient stock if reported.
- Do not invent a currency or VAT rate; ask if VAT is requested without a rate.
- Keep your answers short and factual.
- Do not answer any question unrelated to the inventory task.
"""

MAX_STEPS = 5

def get_client():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("<") or key == "your-api-key-here":
        raise ValueError("Set GEMINI_API_KEY in .env to your Google Gemini API key.")
    return genai.Client(api_key=key)


def run_agent(user_message, previous_interaction_id=None, verbose=False):
    """Send a message to the agent and run tools until it produces an answer."""

    if os.getenv("AI_PROVIDER", "gemini").lower() == "ollama":
        from .llama_agent import run_llama
        return run_llama(user_message, previous_interaction_id, verbose)
    if not isinstance(previous_interaction_id, str):
        previous_interaction_id = None
    client = get_client()
    interaction = client.interactions.create(
        model=MODEL,
        input=user_message,
        tools=TOOL_DECLARATIONS,
        system_instruction=SYSTEM_PROMPT,
        previous_interaction_id=previous_interaction_id,
    )

    for _ in range(MAX_STEPS):
        calls = [s for s in interaction.steps if s.type == "function_call"]

        if not calls:
            return interaction.output_text, interaction.id

        results = []
        for call in calls:
            # Gemini may qualify declared tool names with its API namespace.
            name = call.name.removeprefix("default_api:")
            function = TOOL_FUNCTIONS.get(name)
            if function is None:
                output = {"error": f"Unknown inventory tool: {call.name}"}
            else:
                output = function(**call.arguments)

            if verbose:
                print(f"  -> {call.name}({call.arguments}) = {output}")

            results.append({
                "type": "function_result",
                "name": call.name,
                "call_id": call.id,
                "result": [{"type": "text", "text": json.dumps(output)}],
            })

        interaction = client.interactions.create(
            model=MODEL,
            input=results,
            tools=TOOL_DECLARATIONS,
            system_instruction=SYSTEM_PROMPT,
            previous_interaction_id=interaction.id,
        )

    return "I got stuck working on that. Please try rephrasing.", interaction.id