# FitFindr

A multi-tool AI agent that searches secondhand clothing listings and generates outfit ideas based on your existing wardrobe.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`). Type a query describing what you're looking for — include size and budget if you want to filter results. Toggle between "Example wardrobe" and "Empty wardrobe" to see how outfit suggestions change.

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Filters the 40 mock listings in `data/listings.json` to find items matching the user's style intent, size, and budget.

**Inputs:**
- `description` (`str`): Free-text style description (e.g. `"vintage graphic tee"`). Matched against title, description, category, style tags, and colors.
- `size` (`str | None`): Size filter. Case-insensitive substring match — `"M"` matches `"S/M"` and `"M/L"`. Pass `None` to skip.
- `max_price` (`float | None`): Maximum price inclusive. Pass `None` to skip.

**Output:** `list[dict]` — matching listings sorted by relevance score (keyword overlap count), highest first. Each dict contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` on no match — never raises.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Uses Groq (llama-3.3-70b-versatile) to suggest outfit pairings for the selected listing using pieces the user already owns. Falls back to general styling advice if the wardrobe is empty.

**Inputs:**
- `new_item` (`dict`): A single listing dict from `search_listings` (contains `title`, `category`, `colors`, `style_tags`, `size`, `condition`, `price`).
- `wardrobe` (`dict`): A wardrobe dict with key `"items"` mapping to a list of wardrobe-item dicts (`name`, `category`, `colors`, `style_tags`).

**Output:** `str` — a plain-English outfit suggestion naming specific wardrobe pieces and explaining why each pairing works. If the wardrobe is empty, returns general styling advice instead of failing.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Uses Groq to produce a casual Instagram/TikTok-style caption — the shareable "fit card" — that captures the full outfit vibe in 2–4 sentences.

**Inputs:**
- `outfit` (`str`): The outfit suggestion string from `suggest_outfit`.
- `new_item` (`dict`): The listing the user is considering (used for `title`, `price`, `platform`, `colors`, `style_tags`).

**Output:** `str` — a conversational OOTD caption that mentions the item name, price, and platform once each and captures the outfit's specific vibe. Uses `temperature=1.0` to ensure variety.

---

## How the Planning Loop Works

The loop runs once per user query and makes a sequence of decisions, not just function calls:

**Step 1 — Parse intent.** The agent sends the raw query to Groq and requests structured JSON with three fields: `description`, `size`, and `max_price`. If Groq returns malformed JSON or a field is missing, the parser falls back to using the full raw query as the description with `size=None` and `max_price=None`. This fallback means a parse failure never blocks the search.

**Step 2 — Search.** `search_listings` runs with the parsed parameters. The agent then checks the result count — this is the only branch point in the loop:
- **Empty list:** The agent composes a specific error message (naming which filters were active) and returns early. It does **not** proceed to `suggest_outfit` with an empty item.
- **One or more results:** The agent picks the top result (highest relevance score) and continues.

**Step 3 — Outfit suggestion.** `suggest_outfit` receives the chosen listing and the session wardrobe. The wardrobe is locked in at session start and never changes. The agent does not make any decisions here — it always calls this tool and passes the output forward regardless of whether the wardrobe was empty.

**Step 4 — Fit card.** `create_fit_card` always runs as long as Step 3 produced a non-empty string. The fit card is what gets displayed to the user as the primary output.

The agent does **not** loop or retry within a single query. Relaxing constraints is the user's responsibility — the error message from Step 2 tells them which filter to relax.

---

## State Management

The session dict is the single source of truth for one `run_agent` call:

```python
session = {
    "query": str,             # original user query
    "parsed": dict,           # description, size, max_price extracted by LLM
    "search_results": list,   # all listings returned by search_listings
    "selected_item": dict,    # the top result, passed to suggest_outfit
    "wardrobe": dict,         # user's wardrobe — read-only throughout the loop
    "outfit_suggestion": str, # string returned by suggest_outfit
    "fit_card": str,          # string returned by create_fit_card
    "error": str | None,      # set only when the loop exits early (no results)
}
```

Data flows forward through the session — each tool reads from an earlier field and writes to its own field. No tool reads its own previous output. The wardrobe is loaded once by the caller (from `get_example_wardrobe()` or `get_empty_wardrobe()`) and passed in; the loop never mutates it.

`app.py` reads three final fields to populate the three UI panels: `selected_item` (formatted inline), `outfit_suggestion`, and `fit_card`. It reads `error` first and surfaces it in the first panel if set.

---

## Error Handling

| Tool | Failure mode | What the agent does |
|------|-------------|---------------------|
| `_parse_query` | Groq returns malformed JSON or a field is missing | `except` block catches `json.JSONDecodeError`, `KeyError`, `TypeError`, `ValueError` and returns `{"description": query, "size": None, "max_price": None}` — the search runs with the raw query as the description |
| `search_listings` | No listings match the filters | Returns `[]`; the agent sets `session["error"]` to a message specifying which filters were active and returns early. Example: `'No listings matched "designer ballgown" in size XXS under $5.'` |
| `suggest_outfit` | Wardrobe `items` list is empty | The LLM prompt switches to a general-styling-advice mode: `"Their wardrobe is empty. Give them general styling advice..."` — `create_fit_card` still runs with this response, so the user gets a fit card |
| `create_fit_card` | `outfit` string is empty or whitespace | Returns the string `"Error: No outfit suggestion available — cannot generate a fit card without styling context."` without calling Groq |

**Concrete example from testing:** Running the query `"designer ballgown size XXS under $5"` (included as an example query in `app.py`) returns an empty list from `search_listings` because the dataset contains no ballgowns near that price point. The agent surfaced: `No listings matched your search for "designer ballgown" in size XXS under $5. Try broadening your style keywords, raising your price ceiling, or loosening your size requirement.` The first panel showed this message; the outfit and fit card panels were empty strings.

---

## Spec Reflection

The planning.md spec and the final implementation match on overall structure but differ on two points:

**1. `suggest_outfit` return type.** The spec said it would return a dict with `"outfit"` (list of wardrobe-item dicts) and `"rationale"` (string). The implementation returns a single string that combines both — the LLM writes the suggestion and the reasoning together in one response. This simplified `create_fit_card`, which no longer needs to accept a separate `rationale` argument; it receives the full suggestion string and builds the caption from it. The tradeoff is that the wardrobe items are embedded in prose rather than returned as a structured list, making them harder to inspect programmatically.

**2. `create_fit_card` output format.** The spec described a fixed ASCII box layout (`╔══╗` style). The implementation instead generates a free-form LLM caption at `temperature=1.0`. This was changed because an LLM-generated caption reads more naturally as a "shareable" output and sounds different each time, matching the spec's stated goal of sounding like a real OOTD post.

**3. `get_listing_detail` not implemented.** This fourth tool was planned to let users drill into a specific search result by ID. It was dropped because the Gradio app automatically selects the top result rather than presenting a list for the user to choose from — the lookup is no longer needed.

---

## AI Usage

### Instance 1: Tool implementation from spec

**Input given to AI:** The Tool 1 section of `planning.md` (the `search_listings` spec), the `load_listings()` function signature from `utils/data_loader.py`, and the instruction to implement the function with the five-step TODO in `tools.py`.

**What AI produced:** A function that loaded listings, filtered by price and size, then sorted the filtered results by price ascending (as the spec said "sorted by price ascending").

**What I changed:** The spec said to sort by price, but sorting by keyword relevance score makes the agent return the best match first, not the cheapest match. I overrode the sort to rank by keyword overlap count — the listing with the most matching terms in title, description, style tags, colors, and category scores highest. This made the selected item in the planning loop the most stylistically relevant result rather than just the cheapest one that cleared the filters.

### Instance 2: Planning loop implementation

**Input given to AI:** The Planning Loop and State Management sections of `planning.md`, the signatures and docstrings of all three tool functions, the `_new_session` helper, and the seven-step TODO in `run_agent`.

**What AI produced:** A complete `run_agent` implementation that called `_parse_query`, then `search_listings`, then checked for empty results, then called `suggest_outfit` and `create_fit_card` in sequence, and stored each result in the session dict.

**What I changed:** The generated code passed the raw query string directly to `search_listings` as the description. I restructured it to call `_parse_query` first and pass `parsed["description"]` instead — this is what lets the LLM extract a clean style phrase (`"vintage graphic tee"`) from a full natural-language sentence (`"I'm looking for a vintage graphic tee under $30 in size M, something I can wear to a concert"`). Without this step, the keyword scoring in `search_listings` dilutes across filler words and returns lower-quality matches.
