# Imports

# > Standard Library
import re
import urllib.parse
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

import requests

# > Third-party Libraries
from bs4 import BeautifulSoup

# > Local Dependencies
from .config.ConfigManager import ConfigManager

_cfg = ConfigManager()
WIKI_BASE_URL = _cfg.get_str(
    "WikiSettings", "wiki_base_url", fallback="https://lotro-wiki.com"
)
MISSING_TEXT_INDICATOR = _cfg.get_str(
    "WikiSettings",
    "missing_text_indicator",
    fallback="There is currently no text in this page",
)

# Cache to prevent repeated network calls
WIKI_CACHE = {}


def clean_string_with_mapping(text: str) -> Tuple[str, List[int]]:
    """
    Cleans text (lowercase, alphanumeric + space only) but keeps a map pointing back to original indices.

    Parameters
    ----------
    text : str
        The raw text string.

    Returns
    -------
    Tuple[str, List[int]]
        (cleaned_text, mapping_list)
        mapping_list[i] gives the index in the original string for the i-th character in cleaned_text.
    """
    valid = "abcdefghijklmnopqrstuvwxyz0123456789 "
    cleaned = []
    mapping = []
    text_flat = text.replace("\n", " ")

    for i, char in enumerate(text_flat):
        c_lower = char.lower()
        if c_lower in valid:
            if c_lower == " " and cleaned and cleaned[-1] == " ":
                continue
            cleaned.append(c_lower)
            mapping.append(i)
    return "".join(cleaned), mapping


def clean_string_simple(text: str) -> str:
    """
    Returns just the cleaned string without the index mapping.
    """
    return clean_string_with_mapping(text)[0]


def has_name_placeholder(text: str) -> bool:
    """
    Checks if the text contains any known player name placeholders (e.g. <name>, [name]).
    """
    placeholders = ["<name>", "&lt;name&gt;", "[name]", "(name)"]
    return any(p in text for p in placeholders)


def fuzzy_align_text(
    ocr_text: str, wiki_text: str, is_bestowal: bool = False
) -> Tuple[float, str]:
    """
    Aligns OCR text with Wiki text using SequenceMatcher and smart trimming.

    Parameters
    ----------
    ocr_text : str
        The text detected via OCR.
    wiki_text : str
        The reference text from the Wiki.
    is_bestowal : bool
        If True, returns the full wiki text instead of attempting to trim.

    Returns
    -------
    Tuple[float, str]
        (similarity_score, best_matching_text)
    """
    # 1. Bestowal Mode: Return Full Text
    if is_bestowal:
        score = (
            SequenceMatcher(
                None, clean_string_simple(ocr_text), clean_string_simple(wiki_text)
            ).ratio()
            * 100
        )
        return score, wiki_text

    # 2. Objective Mode: Trim logic
    clean_ocr = clean_string_simple(ocr_text)
    clean_wiki, wiki_map = clean_string_with_mapping(wiki_text)

    if len(clean_ocr) < 10 or len(clean_wiki) < 10:
        return 0.0, ""

    matcher = SequenceMatcher(None, clean_ocr, clean_wiki)
    match = matcher.find_longest_match(0, len(clean_ocr), 0, len(clean_wiki))

    if match.size < 15:
        return 0.0, ""

    clean_wiki_start = max(0, match.b - match.a)
    clean_wiki_end = min(len(clean_wiki), clean_wiki_start + len(clean_ocr))

    orig_start = wiki_map[clean_wiki_start] if clean_wiki_start < len(wiki_map) else 0
    orig_end = (
        wiki_map[clean_wiki_end] if clean_wiki_end < len(wiki_map) else len(wiki_text)
    )

    candidate_text = wiki_text[orig_start:orig_end]

    # --- Smart Trimming (Fix artifacts like "Ca") ---
    trim_match = re.search(r'([.!?]["\']?)\s*(\w{1,5})$', candidate_text)
    if trim_match:
        end_offset = trim_match.start(2)
        candidate_text = candidate_text[:end_offset].strip()
        orig_end = orig_start + len(candidate_text)

    # --- Smart Extension (Fix cut-offs) ---
    if not re.search(r'[.!?]["\']?$', candidate_text.strip()):
        look_ahead_limit = 100
        current_idx = orig_end
        while (
            current_idx < len(wiki_text) and current_idx < orig_end + look_ahead_limit
        ):
            char = wiki_text[current_idx]
            current_idx += 1
            if char in ".!?":
                if current_idx < len(wiki_text) and wiki_text[current_idx] in "'\"":
                    current_idx += 1
                candidate_text = wiki_text[orig_start:current_idx]
                break

    if candidate_text.lstrip().startswith(":"):
        candidate_text = candidate_text.lstrip()[1:].strip()

    score = (
        SequenceMatcher(None, clean_ocr, clean_string_simple(candidate_text)).ratio()
        * 100
    )
    return score, candidate_text


def handle_special_search(search_url: str) -> Optional[str]:
    """
    Handles Wiki 'Special:Search' redirects by scraping the search results page.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=5)
        if "There were no results matching the query" in response.text:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        heading = soup.find("div", class_="mw-search-result-heading")
        if heading:
            link = heading.find("a")
            if link and "href" in link.attrs:
                return WIKI_BASE_URL + link["href"]
        return None
    except Exception as e:
        print(f"Error handling special search: {e}")
        return None


def fetch_quest_stages(wiki_url: str, search_fallback: bool = True) -> dict:
    """
    Scrapes the Wiki page for Quest stages (Background, Objectives, Bestowal).

    Parameters
    ----------
    wiki_url : str
        The wiki page URL to scrape.
    search_fallback : bool
        If True and the direct URL yields no data, try the wiki search
        as a fallback.

    Returns
    -------
    dict
        {stage_name: stage_text}
    """
    if not wiki_url:
        return {}
    if wiki_url in WIKI_CACHE:
        return WIKI_CACHE[wiki_url]

    if "Special:Search" in wiki_url:
        resolved = handle_special_search(wiki_url)
        if not resolved:
            WIKI_CACHE[wiki_url] = {}
            return {}
        wiki_url = resolved

    stages = _scrape_quest_page(wiki_url)

    # If direct URL yielded nothing, try search fallback
    if not stages and search_fallback:
        # Extract quest name from URL for search
        slug = wiki_url.split("/Quest:")[-1] if "/Quest:" in wiki_url else ""
        if slug:
            search_name = slug.replace("_", " ")
            query = urllib.parse.quote_plus(search_name)
            search_url = (
                f"{WIKI_BASE_URL}/w/index.php?title=Special:Search&search={query}"
            )
            resolved = handle_special_search(search_url)
            if resolved:
                stages = _scrape_quest_page(resolved)

    WIKI_CACHE[wiki_url] = stages
    return stages


def _scrape_quest_page(wiki_url: str) -> dict:
    """Fetch and parse a single wiki page into quest stages."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(wiki_url, headers=headers, timeout=3)
        if "localized depending on the race" in response.text:
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        stages = {}
        content_area = soup.find("div", {"id": "mw-content-text"})

        if content_area:
            current_stage = "Intro"
            current_text = []
            seen_lines = set()

            for elem in content_area.find_all(["h2", "h3", "h4", "p", "dd"]):
                if elem.name in ["h2", "h3", "h4"]:
                    if current_text:
                        key = current_stage
                        count = 2
                        while key in stages:
                            key = f"{current_stage} ({count})"
                            count += 1
                        stages[key] = " ".join(current_text)
                    current_stage = elem.get_text(strip=True)
                    current_text = []
                    seen_lines = set()
                elif elem.name in ["p", "dd"]:
                    text = elem.get_text(strip=True)
                    if text and text not in seen_lines:
                        current_text.append(text)
                        seen_lines.add(text)

            if current_text:
                stages[current_stage] = " ".join(current_text)

        return stages
    except Exception as e:
        print(f"Error parsing Wiki page: {e}")
        return {}


def get_best_match(ocr_text: str, stages: dict) -> Tuple[str, str, float]:
    """
    Compares OCR text against all Wiki stages and returns the best match.

    Returns
    -------
    Tuple[str, str, float]
        (stage_name, best_text, accuracy_score)
    """
    best_score = 0.0
    best_stage = "Unknown"
    best_text = ocr_text

    for stage_name, stage_text in stages.items():
        is_bestowal = "Bestowal" in stage_name or "Background" in stage_name
        score, aligned_text = fuzzy_align_text(ocr_text, stage_text, is_bestowal)

        if score > best_score:
            best_score = score
            best_stage = stage_name
            best_text = aligned_text

    return best_stage, best_text, best_score


def _build_wiki_slug(raw_text: str) -> str:
    """Convert an OCR quest title into a wiki URL slug.

    Preserves the original casing of short words (of, the, a, an, in, etc.)
    because MediaWiki URLs are case-sensitive and the wiki uses lowercase
    for these words in page titles.
    """
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,:.-'"
    clean = "".join(c for c in raw_text if c in allowed).strip()
    words = clean.split()

    # Words that should stay lowercase (common in LOTRO wiki page titles)
    lower_words = {
        "of",
        "the",
        "a",
        "an",
        "in",
        "to",
        "for",
        "and",
        "or",
        "at",
        "by",
        "from",
        "with",
        "on",
        "is",
    }

    result = []
    for i, word in enumerate(result if False else words):
        if i > 0 and word.lower() in lower_words:
            result.append(word.lower())
        else:
            result.append(word.capitalize())

    return "_".join(result)


def get_best_wiki_url(raw_text: str) -> str:
    """
    Generates a Wiki URL based on the Quest Title (raw_text).

    No longer makes an HTTP request – just builds the most likely URL.
    The actual page fetch and validation happens in :func:`fetch_quest_stages`
    which handles ``Special:Search`` redirects internally.
    """
    slug = _build_wiki_slug(raw_text)
    return f"{WIKI_BASE_URL}/wiki/Quest:{slug}"
