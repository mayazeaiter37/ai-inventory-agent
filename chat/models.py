from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Item(models.Model):
    name = models.CharField(max_length=100, unique=True)
    quantity = models.IntegerField(default=0)

    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Unit price before VAT; blank means the price is not set.",
    )

    def __str__(self):
        return f"{self.name} ({self.quantity})"
