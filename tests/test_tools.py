# tests/test_tools.py
from unittest.mock import MagicMock, patch

from tools import create_fit_card, search_listings, suggest_outfit


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: no listings match → returns [], no exception
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    # Failure mode: price ceiling must be respected
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("jeans", size="XL", max_price=None)
    assert all("xl" in item["size"].lower() for item in results)


def test_search_returns_list_on_no_keyword_match():
    results = search_listings("zzzzz nonexistent keyword", size=None, max_price=None)
    assert results == []


# ── suggest_outfit ─────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_001",
    "title": "Vintage Levi's 501 Jeans",
    "category": "bottoms",
    "colors": ["blue", "indigo"],
    "style_tags": ["vintage", "denim", "streetwear"],
    "size": "W30 L30",
    "condition": "good",
    "price": 38.0,
    "platform": "depop",
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "White ribbed tank top",
            "category": "tops",
            "colors": ["white"],
            "style_tags": ["basics", "minimal"],
            "notes": None,
        }
    ]
}

EMPTY_WARDROBE = {"items": []}


@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe(mock_client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Pair with the white tank top for a clean street look."
    mock_client.return_value.chat.completions.create.return_value = mock_response

    result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_does_not_crash(mock_client):
    # Failure mode: wardrobe is empty → still returns a non-empty string
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Try pairing with straight-leg trousers and sneakers."
    mock_client.return_value.chat.completions.create.return_value = mock_response

    result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    # Failure mode: empty outfit → returns error message, no exception
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "Error" in result


def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "Error" in result


@patch("tools._get_groq_client")
def test_create_fit_card_returns_caption(mock_client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Found these Levi's on depop for $38 and I'm obsessed."
    mock_client.return_value.chat.completions.create.return_value = mock_response

    result = create_fit_card("White tank + chunky sneakers", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0
