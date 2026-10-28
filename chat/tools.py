from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import Item


def check_stock(name):
    """Look up how many of an item we have."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    return item_details(item)


def list_items():
    """Return every item in the inventory."""
    items = Item.objects.all()
    return {"items": [item_details(i) for i in items]}


def add_item(name, quantity, price=None):
    """Create a new item, or add to an existing one's stock."""
    if type(quantity) is not int or quantity <= 0:
        return {"error": "Quantity must be a positive integer."}
    if price is not None:
        try:
            price = parse_price(price)
        except ValueError as exc:
            return {"error": str(exc)}
    item = Item.objects.filter(name__iexact=name).first()
    if item is not None:
        item.quantity += quantity
        if price is not None:
            item.price = price
        item.save()
        return {**item_details(item), "created": False}
    item = Item.objects.create(name=name, quantity=quantity, price=price)
    return {**item_details(item), "created": True}


def remove_stock(name, quantity):
    """Take a quantity out of stock."""
    if type(quantity) is not int or quantity <= 0:
        return {"error": "Quantity must be a positive integer."}
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    if quantity > item.quantity:
        return {
            "error": f"Cannot remove {quantity}. Only {item.quantity} in stock.",
            "name": item.name,
            "quantity": item.quantity,
        }
    item.quantity -= quantity
    item.save()
    return item_details(item)


def delete_item(name):
    """Remove an item from the inventory entirely."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    item.delete()
    return {"deleted": name}


def item_details(item):
    return {"name": item.name, "quantity": item.quantity,
            "price": str(item.price) if item.price is not None else None}


def parse_price(value):
    try:
        price = Decimal(str(value))
        if not price.is_finite() or not 0 <= price <= Decimal("99999999.99"):
            raise ValueError
        if price != price.quantize(Decimal("0.01")):
            raise ValueError
        return price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("Price must be nonnegative, at most 99999999.99, with at most two decimal places.")


def set_price(name, price):
    """Set an existing item's unit price without changing its stock."""
    try:
        price = parse_price(price)
    except ValueError as exc:
        return {"error": str(exc)}
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    item.price = price
    item.save(update_fields=["price"])
    return item_details(item)


def calculate_cost(name, quantity, vat_percent=0):
    """Quote a quantity at its stored unit price, adding VAT without selling stock."""
    if type(quantity) is not int or not 1 <= quantity <= 1000000000:
        return {"error": "Quantity must be a positive integer no greater than 1000000000."}
    try:
        vat = Decimal(str(vat_percent))
        if not vat.is_finite() or not 0 <= vat <= 100:
            raise ValueError
    except (InvalidOperation, ValueError):
        return {"error": "VAT percentage must be a number from 0 to 100."}
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    if item.price is None:
        return {"error": f"The unit price of '{item.name}' has not been set. Ask the user for it."}
    subtotal = item.price * quantity
    tax = (subtotal * vat / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"name": item.name, "quantity": quantity, "unit_price": str(item.price),
            "subtotal": str(subtotal), "vat_percent": str(vat), "vat_amount": str(tax),
            "total": str(subtotal + tax), "stock_available": item.quantity,
            "enough_stock": item.quantity >= quantity}


TOOL_DECLARATIONS = [
    {
        "type": "function",
        "name": "check_stock",
        "description": "Look up the current quantity of a single item in the inventory. Use this whenever the user asks whether something is in stock or how many there are.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Hammer'.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "type": "function",
        "name": "list_items",
        "description": "Return every item in the inventory with its quantity. Use this when the user asks what is in stock generally, or asks for a list, rather than about one specific item.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "add_item",
        "description": "Add stock to the inventory. If the item does not exist it is created; if it already exists the quantity is added to the existing total. Use this for restocking and for new deliveries.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Hammer'.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many units to add. Must be positive.",
                },
            },
            "required": ["name", "quantity"],
        },
    },
    {
        "type": "function",
        "name": "remove_stock",
        "description": "Reduce the quantity of an existing item. Use this when items are sold, shipped or used. This does NOT delete the item; it only lowers the number.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Hammer'.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many units to remove. Must be positive.",
                },
            },
            "required": ["name", "quantity"],
        },
    },
    {
        "type": "function",
        "name": "delete_item",
        "description": "Permanently remove an item and its record from the inventory entirely. This is destructive. Only use it when the user clearly wants the item gone, not when they want to reduce its quantity.",
        "parameters": {
            "type": "object",
            "properties": {

                "name": {
                    "type": "string",
                    "description": "The name of the item to delete.",
                },
            },
            "required": ["name"],
        },
    },
]

TOOL_FUNCTIONS = {
    "check_stock": check_stock,
    "list_items": list_items,
    "add_item": add_item,
    "remove_stock": remove_stock,
    "delete_item": delete_item,
}

# Extend the starter declarations with pricing operations.
next(t for t in TOOL_DECLARATIONS if t["name"] == "add_item")["parameters"]["properties"]["price"] = {
    "type": "number", "description": "Optional unit price before VAT. Only supply a price given by the user."
}
TOOL_DECLARATIONS.extend([
    {
        "type": "function", "name": "set_price",
        "description": "Set or update an existing item's unit price before VAT without changing stock.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "price": {"type": "number"}},
            "required": ["name", "price"]},
    },
    {
        "type": "function", "name": "calculate_cost",
        "description": "Calculate cost for a quantity using the database unit price, including VAT. Returns subtotal, VAT and total; does not change stock.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "quantity": {"type": "integer"},
            "vat_percent": {"type": "number", "description": "Percentage, e.g. 10 for 10% VAT; defaults to zero."}},
            "required": ["name", "quantity"]},
    },
])
TOOL_FUNCTIONS.update({"set_price": set_price, "calculate_cost": calculate_cost})
