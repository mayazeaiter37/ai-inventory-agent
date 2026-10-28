# EECE430 — AI Inventory Agent (Assignments 3 and 5)

The solution adds an item's unit price and supports cost questions with VAT through the existing Gemini chat.

## Run with Docker (Assignment 5)

The image is built by the `Dockerfile` in this folder and published to GitHub
Container Registry by `.github/workflows/docker.yml` on every push to `main`.
The container applies migrations, creates the demo Chocolate Bar item and
serves the app on port 8000. Your API key is never stored in the image; pass it
when you start the container.

Run the image straight from GitHub:

```sh
docker run -p 8000:8000 -e GEMINI_API_KEY=your-key ghcr.io/mayazeaiter37/ai-inventory-agent:latest
```

Or clone the repository from GitHub and build it yourself:

```sh
git clone https://github.com/mayazeaiter37/ai-inventory-agent.git
cd ai-inventory-agent
docker build -t ai-inventory-agent .
docker run -p 8000:8000 --env-file .env ai-inventory-agent
```

(`--env-file .env` needs a `.env` made from `.env.example`.) Then open
http://localhost:8000/. Stop it in Docker Desktop's Containers tab.

## Run without Docker

Use Python 3.12 or newer. From this `inventory` folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py demo_cost
python manage.py runserver
```

On Windows, activate with `.venv\Scripts\activate` instead.

Edit `.env` to set `GEMINI_API_KEY` to your own Google Gemini API key. `.env.example` shows the format. The supplied placeholder is not a working key. Never submit your real key. Optionally set `GEMINI_MODEL`; the default is `gemini-3.8-flash`.

Open http://127.0.0.1:8000/ for the chat. The local `demo_cost` command works without an API key, creates Chocolate Bar at 2.00 with 10 units only if absent, and preserves an existing item's values.

## Required chat example

After preparing the demo item, send:

> Set the unit price of Chocolate Bar to 2.00.

Then:

> What is the cost of 3 items of chocolate bar after adding 10% VAT?

Expected calculation:

- Unit price before VAT: 2.00
- Subtotal: 3 × 2.00 = 6.00
- VAT: 6.00 × 10 / 100 = 0.60
- Total including VAT: **6.60**

The unit price 2.00 is an explicit example assumption, not a price specified in the assignment. No currency was specified. A quote does not reduce stock.

This is the expected live conversation, not a recorded Gemini response. A live chat requires your API key; local calculations and the mocked chat flow were tested separately.

## Implementation

- `chat/models.py`: `price` is a two-decimal `DecimalField` for the unit price before VAT. Existing items receive a blank price so an unknown price is not treated as free.
- `chat/migrations/0002_item_price.py`: adds the column while preserving existing inventory.
- `chat/tools.py`: stock tools expose prices; `add_item` accepts an optional price; `set_price` updates prices without changing stock; `calculate_cost` reads the stored price and returns subtotal, VAT and total.
- `chat/agent.py`: registers the pricing tools through the existing declarations and instructs Gemini to use the cost tool, ask for unknown prices, and distinguish quotes from sales. API initialization is deferred so migrations and tests work without a key.
- `chat/admin.py`: displays name, quantity and price in the admin list.

Money uses Python `Decimal`, with VAT rounded to two decimal places using `ROUND_HALF_UP`. Quantity must be a positive integer and VAT must be between 0 and 100. An unavailable price or unknown item returns an explanatory error. Quotes also report whether enough stock is available.

The original Gemini Interactions tool loop follows Google's [function calling documentation](https://ai.google.dev/gemini-api/docs/function-calling).

## Verify

```sh
python manage.py test chat
python manage.py check
python manage.py makemigrations --check --dry-run
```

Twelve tests cover the assignment calculation, rounding, unknown prices/items, invalid values, restocking, zero prices, insufficient stock, tool execution with mocked Gemini responses, and chat session rendering. They do not call the external API.

## Optional local Llama 3.1

Install Ollama, run `ollama serve`, and download the model with
`ollama pull llama3.1:8b` (several GB, once). Set these in `.env`:

```env
AI_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
```

Restart Django and click Start over. Requests now run on your computer without
Gemini quota or an API key. The first request loads the model and may be slow.
Set `AI_PROVIDER=gemini` and restart to return to the original provider.
Llama selects and calls the same database tools; it is not a scripted demo.
