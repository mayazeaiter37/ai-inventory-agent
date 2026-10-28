import json
from decimal import Decimal
from django.core.management.base import BaseCommand
from chat.models import Item
from chat.tools import calculate_cost


class Command(BaseCommand):
    help = "Create an example chocolate bar if absent and quote 3 bars with 10% VAT. No API key needed."

    def handle(self, *args, **options):
        item = Item.objects.filter(name__iexact="Chocolate Bar").first()
        if item is None:
            item = Item.objects.create(name="Chocolate Bar", quantity=10, price=Decimal("2.00"))
        self.stdout.write("Local tool demo (not a live Gemini chat). Existing item values are preserved.")
        self.stdout.write(json.dumps(calculate_cost(item.name, 3, 10), indent=2))
