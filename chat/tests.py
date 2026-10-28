import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from .agent import run_agent
from .models import Item
from .tools import add_item, calculate_cost, check_stock, list_items, set_price


class PricingTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(name="Chocolate Bar", quantity=10, price="2.00")

    def test_assignment_calculation_does_not_change_stock(self):
        result = calculate_cost("chocolate bar", 3, 10)
        self.assertEqual((result["subtotal"], result["vat_amount"], result["total"]),
                         ("6.00", "0.60", "6.60"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    def test_rounding(self):
        set_price("Chocolate Bar", "0.05")
        self.assertEqual(calculate_cost("Chocolate Bar", 1, 10)["total"], "0.06")

    def test_missing_item_and_unknown_price(self):
        self.assertIn("error", calculate_cost("missing", 3, 10))
        Item.objects.create(name="Unpriced")
        self.assertIn("not been set", calculate_cost("Unpriced", 3, 10)["error"])

    def test_invalid_quantities_and_vat(self):
        for quantity in (0, -1, 1.5, True, "3"):
            with self.subTest(quantity=quantity):
                self.assertIn("error", calculate_cost("Chocolate Bar", quantity, 10))
        for vat in (-1, 101, "NaN", "Infinity", "oops"):
            with self.subTest(vat=vat):
                self.assertIn("error", calculate_cost("Chocolate Bar", 3, vat))

    def test_price_validation_does_not_change_stock(self):
        for price in (-1, "NaN", "Infinity", "2.005", "100000000"):
            self.assertIn("error", add_item("Chocolate Bar", 2, price))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.item.price = Decimal("-1")
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_restock_preserves_price_and_set_price_preserves_stock(self):
        add_item("chocolate bar", 2)
        self.assertEqual(check_stock("Chocolate Bar")["price"], "2.00")
        self.assertEqual(set_price("Chocolate Bar", "2.50")["quantity"], 12)
        self.assertEqual(list_items()["items"][0]["price"], "2.50")

    def test_new_item_with_price_and_free_item(self):
        self.assertEqual(add_item("Sample", 1, 0)["price"], "0.00")
        self.assertEqual(calculate_cost("Sample", 1)["total"], "0.00")

    def test_quote_reports_insufficient_stock(self):
        result = calculate_cost("Chocolate Bar", 11, 10)
        self.assertFalse(result["enough_stock"])
        self.assertEqual(result["total"], "24.20")

    @patch.dict("os.environ", {"AI_PROVIDER": "gemini"})
    @patch("chat.agent.get_client")
    def test_agent_executes_cost_tool_and_returns_result_to_gemini(self, get_client):
        create = get_client.return_value.interactions.create
        create.side_effect = [
            SimpleNamespace(id="call-1", steps=[SimpleNamespace(
                type="function_call", name="calculate_cost", id="tool-1",
                arguments={"name": "Chocolate Bar", "quantity": 3, "vat_percent": 10})]),
            SimpleNamespace(id="answer-1", steps=[], output_text="Total including VAT: 6.60"),
        ]
        answer, interaction_id = run_agent("What is the cost of 3 chocolate bars with 10% VAT?")
        result = json.loads(create.call_args.kwargs["input"][0]["result"][0]["text"])
        self.assertEqual(result["total"], "6.60")
        self.assertEqual(create.call_args.kwargs["previous_interaction_id"], "call-1")
        self.assertEqual(interaction_id, "answer-1")
        self.assertIn("6.60", answer)

    @patch("chat.views.run_agent", return_value=("Total including VAT: 6.60", "answer-1"))
    def test_chat_renders_answer_and_keeps_session(self, agent):
        response = self.client.post("/", {"message": "Cost of 3 chocolate bars with 10% VAT?"}, follow=True)
        self.assertContains(response, "6.60")
        self.assertEqual(self.client.session["interaction_id"], "answer-1")
        self.assertEqual(len(self.client.session["history"]), 2)


class LlamaTests(TestCase):
    @patch('chat.llama_agent.ollama_chat')
    def test_local_tool_call_and_context(self, chat):
        from .llama_agent import run_llama
        Item.objects.create(name='Chocolate Bar', quantity=10, price='2.00')
        chat.side_effect = [
            {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
                'name': 'calculate_cost', 'arguments': {'name': 'Chocolate Bar', 'quantity': 3, 'vat_percent': 10}}}]},
            {'role': 'assistant', 'content': 'Total: 6.60'},
            {'role': 'assistant', 'content': 'The VAT was 0.60.'},
        ]
        answer, state = run_llama('Cost of 3 chocolate bars with 10% VAT?')
        self.assertEqual(answer, 'Total: 6.60')
        tool_result = json.loads(state['messages'][2]['content'])
        self.assertEqual(tool_result['total'], '6.60')
        answer, state = run_llama('How much was the VAT?', state)
        self.assertEqual(answer, 'The VAT was 0.60.')
        self.assertEqual(state['messages'][0]['role'], 'user')

    @patch('chat.llama_agent.ollama_chat')
    def test_unknown_tool_is_returned_as_error(self, chat):
        from .llama_agent import run_llama
        chat.side_effect = [
            {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'invalid', 'arguments': {}}}]},
            {'role': 'assistant', 'content': 'Unable to run that tool.'},
        ]
        _, state = run_llama('Test')
        self.assertIn('error', json.loads(state['messages'][2]['content']))


class GeminiToolNameTests(TestCase):
    @patch.dict("os.environ", {"AI_PROVIDER": "gemini"})
    @patch("chat.agent.get_client")
    def test_namespaced_stock_tool(self, get_client):
        Item.objects.create(name="Chocolate Bar", quantity=10, price="2.00")
        create = get_client.return_value.interactions.create
        create.side_effect = [
            SimpleNamespace(id="call-1", steps=[SimpleNamespace(
                type="function_call", name="default_api:check_stock", id="tool-1",
                arguments={"name": "Chocolate Bar"})]),
            SimpleNamespace(id="answer-1", steps=[], output_text="10 in stock"),
        ]
        answer, _ = run_agent("Check chocolate bar stock")
        result = create.call_args.kwargs["input"][0]
        self.assertEqual(result["name"], "default_api:check_stock")
        self.assertEqual(result["call_id"], "tool-1")
        self.assertEqual(json.loads(result["result"][0]["text"])["quantity"], 10)
        self.assertEqual(answer, "10 in stock")

    @patch.dict("os.environ", {"AI_PROVIDER": "gemini"})
    @patch("chat.agent.get_client")
    def test_unknown_tool_returns_error_without_crashing(self, get_client):
        create = get_client.return_value.interactions.create
        create.side_effect = [
            SimpleNamespace(id="call-1", steps=[SimpleNamespace(
                type="function_call", name="unknown_tool", id="tool-1", arguments={})]),
            SimpleNamespace(id="answer-1", steps=[], output_text="Unable to use tool"),
        ]
        run_agent("Check stock")
        result = json.loads(create.call_args.kwargs["input"][0]["result"][0]["text"])
        self.assertIn("error", result)
