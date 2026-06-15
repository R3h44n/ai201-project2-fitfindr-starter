# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Filters the 40 mock listings in `data/listings.json` based on user-supplied style keywords, size, and maximum price. Returns all listings that match every supplied filter (filters that are `None` are ignored).

**Input parameters:**
- `style_keywords` (list[str]): One or more keywords to match against each listing's `style_tags`, `category`, `colors`, or `title` (case-insensitive substring match). Example: `["vintage", "denim"]`.
- `size` (str | None): The user's size string. Compared against each listing's `size` field using a loose substring match (e.g. `"M"` matches `"S/M"` and `"M/L"`). Pass `None` to skip size filtering.
- `max_price` (float | None): Upper bound on price (inclusive). Pass `None` to skip price filtering.

**What it returns:**
A list of listing dicts (same fields as `listings.json`: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`). The list is sorted by price ascending. Returns an empty list `[]` if no listings match.

**What happens if it fails or returns nothing:**
If the list is empty, the agent tells the user no listings matched and asks them to relax one constraint at a time — first broaden the style keywords, then raise the price ceiling, then loosen the size requirement. The agent does not call `suggest_outfit` or `create_fit_card` until at least one listing is found.

---

### Tool 2: suggest_outfit

**What it does:**
Given a single new listing the user is considering buying and the user's existing wardrobe, selects up to 3 wardrobe items that complement the new piece and explains why each pairing works (color harmony, style cohesion, occasion fit).

**Input parameters:**
- `new_item` (dict): A single listing dict returned by `search_listings` (contains `title`, `category`, `colors`, `style_tags`, etc.).
- `wardrobe` (dict): A wardrobe object in the format defined by `wardrobe_schema.json` — a dict with key `"items"` whose value is a list of wardrobe-item dicts (`id`, `name`, `category`, `colors`, `style_tags`, `notes`).

**What it returns:**
A dict with two keys:
- `"outfit"`: a list of wardrobe-item dicts chosen from `wardrobe["items"]` that pair best with the new item (0–3 items, one per wardrobe category: tops, bottoms, shoes, accessories — excluding the category of the new item itself).
- `"rationale"`: a plain-English string (2–4 sentences) explaining why this combination works — referencing specific colors and style tags.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the agent returns `{"outfit": [], "rationale": "Your wardrobe is empty — the fit card will show the new item on its own. Consider telling me what you already own so I can suggest pairings."}`. The agent still proceeds to `create_fit_card` with the new item alone so the user gets a useful output.

---

### Tool 3: create_fit_card

**What it does:**
Formats the new listing and the suggested wardrobe pairings into a structured, readable "fit card" that the user can screenshot or share — showing the full outfit at a glance with price, condition, and platform details for the new item.

**Input parameters:**
- `new_item` (dict): The listing the user is considering (same dict from `search_listings`).
- `outfit` (list[dict]): The list of wardrobe items returned by `suggest_outfit` (may be empty).
- `rationale` (str): The pairing explanation from `suggest_outfit`.

**What it returns:**
A formatted multi-line string (the fit card). Layout:

```
╔══════════════════════════════════════════╗
║  ✦ FIT CARD                             ║
╠══════════════════════════════════════════╣
║  NEW FIND                               ║
║  [title]                                ║
║  [price] · [condition] · [platform]     ║
║  Sizes: [size]  Colors: [colors]        ║
╠══════════════════════════════════════════╣
║  PAIR WITH (from your wardrobe)         ║
║  • [item 1 name]                        ║
║  • [item 2 name]                        ║
║  • [item 3 name]                        ║
╠══════════════════════════════════════════╣
║  WHY IT WORKS                           ║
║  [rationale]                            ║
╚══════════════════════════════════════════╝
```

If `outfit` is empty, the "PAIR WITH" section reads `"No wardrobe items yet — style it your way!"`.

**What happens if it fails or returns nothing:**
If `new_item` is missing required fields, the agent fills in `"N/A"` for the missing values and still renders the card so the user sees something useful. The agent logs a warning message above the card indicating which fields were absent.

---

### Additional Tools (if any)

### Tool 4: get_listing_detail

**What it does:**
Looks up a single listing by its `id` and returns the full listing dict. Used when the user asks for more information about a specific search result after seeing the summary list.

**Input parameters:**
- `listing_id` (str): The `id` field of the listing (e.g. `"lst_007"`).

**What it returns:**
The full listing dict if found, or `None` if no listing with that id exists.

**What happens if it fails or returns nothing:**
If `None` is returned, the agent tells the user the id wasn't recognized and shows the list of valid ids from the most recent search.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent follows a linear pipeline with one branch point:

1. **Parse user intent.** The agent extracts `style_keywords`, `size`, and `max_price` from the user's natural-language message. If any value is ambiguous it asks one clarifying question before proceeding.

2. **Call `search_listings`.** Always the first tool call. The agent inspects the result:
   - If empty → ask the user to relax a constraint; loop back to step 2.
   - If 1–3 results → pick the top result (cheapest that meets all filters) and proceed.
   - If 4+ results → summarize the top 3 to the user, ask which they want to explore, then proceed with the chosen one.

3. **Call `suggest_outfit`** with the chosen listing and the session wardrobe. The wardrobe starts as the `example_wardrobe` from `wardrobe_schema.json` (or an empty wardrobe if the user provided none).

4. **Call `create_fit_card`** with the listing, the outfit list, and the rationale from step 3.

5. **Present the fit card** to the user. The agent then asks: "Want to explore another item from the results, or adjust your search?" If yes, loop back to step 2 or 3 as appropriate. If no, the session ends.

The agent knows it is "done" when the user signals satisfaction (e.g. "that's great", "thanks") or explicitly ends the conversation.

---

## State Management

**How does information from one tool get passed to the next?**

The agent maintains a session state dict that accumulates across tool calls:

```python
state = {
    "last_search_results": [],   # list of listings from the most recent search_listings call
    "selected_item": None,       # the single listing the user chose to explore
    "wardrobe": {...},           # the user's wardrobe (loaded once at session start)
    "last_outfit": [],           # wardrobe items returned by suggest_outfit
    "last_rationale": "",        # explanation string from suggest_outfit
    "last_fit_card": "",         # rendered string from create_fit_card
}
```

- `search_listings` writes to `state["last_search_results"]` and sets `state["selected_item"]` to the top result (or the user's chosen result).
- `suggest_outfit` reads `state["selected_item"]` and `state["wardrobe"]`; writes to `state["last_outfit"]` and `state["last_rationale"]`.
- `create_fit_card` reads `state["selected_item"]`, `state["last_outfit"]`, and `state["last_rationale"]`; writes to `state["last_fit_card"]`.
- If the user asks to see details on a result, `get_listing_detail` reads from `state["last_search_results"]` to validate the id.

The wardrobe is never mutated during a session — it is read-only input data.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Agent tells the user which filter likely eliminated all results (price is the most common culprit), suggests raising max_price by $10 or broadening style keywords, and offers to re-run automatically with the relaxed filter. |
| suggest_outfit | Wardrobe is empty (`items: []`) | Agent returns an empty outfit list with an explanatory rationale string, then calls `create_fit_card` anyway so the user still gets a formatted output for the new item. Agent also prompts the user to describe what they own so future calls can generate real pairings. |
| create_fit_card | Outfit input is missing or incomplete (`new_item` has null fields) | Agent substitutes `"N/A"` for each missing field and renders the card. A one-line warning is prepended: `"⚠ Some item details were missing and have been marked N/A."` |
| get_listing_detail | `listing_id` not found in data | Agent responds: `"I couldn't find listing [id]. Here are the ids from your last search: [list]."` and invites the user to pick again. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                               │
│  "I want a vintage graphic tee under $30, size M,              │
│   to wear with my baggy jeans and chunky sneakers"             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PLANNING LOOP                               │
│  1. Parse intent → extract keywords, size, max_price           │
│  2. Decide which tool to call based on session state           │
│  3. Update state after each tool call                          │
│  4. Check stop condition (user satisfied / no more results)    │
└──────┬──────────────┬───────────────────┬───────────────────────┘
       │              │                   │
       ▼              ▼                   ▼
┌────────────┐ ┌──────────────┐ ┌──────────────────┐
│  search_   │ │ suggest_     │ │  create_fit_card  │
│  listings  │ │ outfit       │ │                  │
│            │ │              │ │  new_item +       │
│  keywords  │ │  new_item +  │ │  outfit list +   │
│  size      │ │  wardrobe    │ │  rationale       │
│  max_price │ │              │ │                  │
│            │ │  → outfit    │ │  → fit card      │
│  → list of │ │  → rationale │ │    (text)        │
│    listings│ └──────┬───────┘ └────────┬─────────┘
└─────┬──────┘        │                  │
      │               │                  │
      │        ┌──────▼──────────────────▼──────┐
      │        │         SESSION STATE           │
      └───────►│  last_search_results            │
               │  selected_item                  │
               │  wardrobe  (read-only)          │
               │  last_outfit                    │
               │  last_rationale                 │
               │  last_fit_card                  │
               └─────────────────────────────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │   OUTPUT TO USER       │
               │   Rendered fit card    │
               │   + follow-up prompt   │
               └────────────────────────┘

Error paths:
  search_listings → [] ──────────────────► ask user to relax constraint → loop
  suggest_outfit  → wardrobe empty ──────► empty outfit, still call create_fit_card
  create_fit_card → missing fields ──────► fill N/A, prepend warning, render anyway
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **`search_listings`**: Give Claude the Tool 1 spec above (inputs, return format, failure mode) plus the `load_listings()` function signature from `utils/data_loader.py`. Ask it to implement `search_listings(style_keywords, size, max_price)` that loads the JSON once and filters in memory. Verify by running 3 manual test cases: (1) `["vintage", "graphic tee"]`, size `"L"`, max `$25` → should return `lst_006` and `lst_033`; (2) `["cottagecore"]`, size `None`, max `$20` → should return `lst_002`; (3) `["y2k"]`, size `"XS"`, max `$50` → should return `[]`.

- **`suggest_outfit`**: Give Claude the Tool 2 spec, the wardrobe schema, and the example wardrobe. Ask it to implement `suggest_outfit(new_item, wardrobe)` that picks at most one wardrobe item per missing category and writes a rationale by matching `style_tags` and `colors`. Verify by passing `lst_006` (black grunge graphic tee, size L) with the example wardrobe — expect it to suggest `w_001` (baggy dark wash jeans), `w_007` or `w_008` (sneakers or boots), and `w_010` (crossbody bag).

- **`create_fit_card`**: Give Claude the Tool 3 spec with the exact ASCII template above. Ask it to implement `create_fit_card(new_item, outfit, rationale)` as a pure string-formatting function with no external dependencies. Verify by calling it with the output of the two steps above and checking that every field appears in the output and no `KeyError` is raised when a field is `None`.

- **`get_listing_detail`**: Give Claude the Tool 4 spec. Ask for a one-function implementation that calls `load_listings()` and returns the dict matching the given id or `None`. Verify with `lst_001` (should return data) and `lst_999` (should return `None`).

**Milestone 4 — Planning loop and state management:**

Give Claude the Planning Loop and State Management sections above, plus all four implemented tool functions. Ask it to implement a `run_agent(user_message, state)` function that: (1) uses an LLM call (Groq) to extract `style_keywords`, `size`, `max_price` from the user message; (2) calls tools in the order described; (3) updates `state` after each call; (4) returns the final fit card string. Verify end-to-end with the example query below, checking that the fit card contains the expected listing title and at least one wardrobe item name.

---

## A Complete Interaction (Step by Step)

FitFindr takes a user's natural-language request — style preferences, size, and budget — and runs it through three tools in sequence: `search_listings` is triggered first to find real matching listings from the dataset (it never invents items that don't exist), then `suggest_outfit` is triggered once a listing is selected to pair it with pieces the user already owns, and finally `create_fit_card` is triggered to format everything into a shareable outfit summary. When something fails, the agent practices graceful degradation — if `search_listings` returns nothing it acknowledges the gap and asks the user to relax one constraint rather than silently stopping; if `suggest_outfit` receives an empty wardrobe it skips pairings but still passes the new item to `create_fit_card` so the user gets something useful; if `create_fit_card` has incomplete data it substitutes "N/A" with a warning rather than either inventing details or refusing to render.
