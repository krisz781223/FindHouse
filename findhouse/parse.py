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
    tail = tail.split("telekméret", 1)[0]
    m = re.search(r"(\d{2,4})\s*m\s*(?:2|²)", tail)   # "130 m2", "130 m²" or "130 m<sup>2</sup>"
    if m:
        out["m2"] = int(m.group(1))
    elif out["price"]:
        # fallback: price / (Ft per m²) shown on the card
        pm = re.search(r"(\d{1,3}(?:[ \u00a0]\d{3})+)\s*Ft\s*/\s*m", t)
        if pm:
            ppm = int(re.sub(r"\D", "", pm.group(1)))
            if ppm > 50000:
                out["m2"] = round(out["price"] * 1e6 / ppm)
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


ZARTKERT = re.compile(r"zártkert|külterület|zárt kert", re.I)
CONDITIONS = ["Új építésű", "Újszerű", "Felújított", "Jó állapotú", "Közepes állapotú", "Átlagos", "Felújítandó",
              "Befejezetlen", "Bontandó"]


def _label(text: str, label: str) -> str | None:
    m = re.search(rf"{label}\s*:?\s*\n?\s*([^\n]+)", text)
    return m.group(1).strip() if m else None


def parse_detail_page(html: str) -> dict:
    """Read the attributes a list card does not show: condition, floor area, plot, zártkert hints.

    Only the listing's own parts are used (the "Részletes adatok" block, the header and the
    description), so menus or search filters elsewhere on the page cannot leak in."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "footer", "form"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    details = text.split("Részletes adatok", 1)[-1] if "Részletes adatok" in text else text
    out = {"condition": None, "m2": None, "telek": None, "zartkert": False}
    for m in re.finditer(r"Állapot\s*:\s*\n?\s*([^\n]+)", details):
        v = m.group(1).strip()
        hit = next((c for c in CONDITIONS if v.lower().startswith(c.lower())), None)
        if hit or (2 < len(v) < 30 and not v.endswith(":")):
            out["condition"] = hit or v[0].upper() + v[1:]
            break
    out["v"] = 2
    m = re.search(r"\n(\d{2,4})\s*m²\s*\n", "\n" + text + "\n")
    if m:
        out["m2"] = int(m.group(1))
    tel = _label(details, r"Telekméret")
    if tel:
        mm = re.search(r"(\d[\d\s.]*)\s*(m2|m²|ha)", tel)
        if mm:
            v = float(re.sub(r"[\s.]", "", mm.group(1)))
            out["telek"] = int(v * 10000) if mm.group(2) == "ha" else int(v)
    # zártkert/külterület: only in the description (longest leaf text block) and the meta description
    leaves = [el.get_text(" ", strip=True) for el in soup.find_all(["p", "div"])
              if not el.find(["p", "div", "section", "ul"])]
    desc = max(leaves, key=len) if leaves else ""
    meta = soup.find("meta", attrs={"name": "description"})
    desc += " " + (meta.get("content", "") if meta else "")
    out["zartkert"] = bool(ZARTKERT.search(desc))
    return out
