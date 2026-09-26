"""Parse koltozzbe.hu list pages into listing dicts.

The parser does not depend on CSS class names: it looks for links that point to a
listing (…/elado-csaladi_haz-<slug>/h<digits>) and reads the numbers out of the
link's visible text, e.g.
  "98.5 M Ft 684 028 Ft/m2 Pomáz - Eladó családi ház … 4 szoba144 m2telekméret:748 m² építés éve:1995"
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

PRICE = re.compile(r"(\d+(?:[.,]\d+)?)\s*M\s*Ft")
ROOMS = re.compile(r"(\d+(?:\s*\+\s*\d+)?)\s*szoba(?!s)")
TELEK = re.compile(r"telekméret:\s*(\d+(?:[.,]\d+)?)\s*(m²|m2|ha)")
YEAR = re.compile(r"építés éve:\s*(\d{4})")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_card_text(text: str) -> dict:
    """Extract fields from the visible text of one listing card."""
    t = re.sub(r"\s+", " ", text).strip()
    out = {"price": None, "rooms": None, "m2": None, "telek": None, "year": None, "note": ""}
    m = PRICE.search(t)
    if m:
        out["price"] = _num(m.group(1))
    m = ROOMS.search(t)
    if m:
        out["rooms"] = re.sub(r"\s", "", m.group(1))
    # m2: the number right before "m2" that is not part of "Ft/m2"
    tail = t.split("szoba", 1)[-1] if "szoba" in t else t
    m = re.search(r"(\d{2,4})\s*m2", tail)
    if m:
        out["m2"] = int(m.group(1))
    m = TELEK.search(t)
    if m:
        v = _num(m.group(1))
        out["telek"] = int(v * 10000) if m.group(2) == "ha" else int(v)
    m = YEAR.search(t)
    if m:
        out["year"] = int(m.group(1))
    # description = text after the last "Eladó családi ház" label, up to the "..." cut
    parts = re.split(r"Eladó (?:családi ház|ikerház|sorház)", t)
    if len(parts) > 1:
        desc = re.split(r"\.\.\.|…", parts[-1])[0].strip(" ,-")
        out["note"] = desc[:120]
    return out


def parse_list_page(html: str, slug: str) -> tuple[list[dict], int]:
    """Return (listings, last_page_number) for one list page."""
    soup = BeautifulSoup(html, "html.parser")
    href_re = re.compile(rf"/elado-csaladi_haz-{re.escape(slug)}/(h\d+)")
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        m = href_re.search(a["href"])
        if not m:
            continue
        text = a.get_text(" ", strip=True)
        if "M Ft" not in text:
            continue
        lid = m.group(1)
        rec = parse_card_text(text)
        rec["id"] = lid
        rec["url"] = f"https://koltozzbe.hu/elado-csaladi_haz-{slug}/{lid}"
        # keep the richest version if the same card is linked twice
        if lid not in seen or sum(v is not None for v in rec.values()) > sum(v is not None for v in seen[lid].values()):
            seen[lid] = rec
    last = 1
    for a in soup.find_all("a", href=True):
        pm = re.search(r"[?&]page=(\d+)", a["href"])
        if pm:
            last = max(last, int(pm.group(1)))
    return list(seen.values()), last
