"""Download all list pages for the configured areas (politely) and return raw listings."""
from __future__ import annotations
import random, time, logging
import requests
from .parse import parse_list_page, parse_detail_page

log = logging.getLogger(__name__)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) FindHouse personal house search (1 request / few seconds)",
    "Accept-Language": "hu-HU,hu;q=0.9",
}


def fetch(session: requests.Session, url: str, tries: int = 3) -> str | None:
    for i in range(tries):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.text
            log.warning("HTTP %s for %s", r.status_code, url)
            if r.status_code in (403, 429):
                time.sleep(30 * (i + 1))
        except requests.RequestException as e:
            log.warning("error %s for %s", e, url)
        time.sleep(5 * (i + 1))
    return None


def scrape_area(session, cfg: dict, area: dict) -> tuple[list[dict], dict]:
    base = f"{cfg['source']}/elado-csaladi_haz-{area['slug']}"
    lo, hi = cfg["request_delay_seconds"]
    rows, stats = [], {"pages": 0, "failed": []}
    page, last = 1, 1
    while page <= min(last, cfg["max_pages_per_area"]):
        url = base if page == 1 else f"{base}?page={page}"
        html = fetch(session, url)
        stats["pages"] += 1
        if html is None:
            stats["failed"].append(page)
        else:
            items, last_seen = parse_list_page(html, area["slug"])
            last = max(last, last_seen)
            for it in items:
                it["area"] = area["name"]
            rows.extend(items)
        page += 1
        time.sleep(random.uniform(lo, hi))
    return rows, stats


def scrape_all(cfg: dict) -> tuple[list[dict], dict]:
    session = requests.Session()
    all_rows, report = [], {}
    for area in cfg["areas"]:
        rows, stats = scrape_area(session, cfg, area)
        log.info("%s: %d pages, %d cards, failed=%s", area["name"], stats["pages"], len(rows), stats["failed"])
        report[area["name"]] = {**stats, "cards": len(rows)}
        all_rows.extend(rows)
    return all_rows, report


def detail_candidates(state: dict, cfg: dict, today: str) -> list[dict]:
    """Active listings in the configured areas, cheap enough to matter, without fresh details."""
    import datetime as dt
    areas = {a["name"] for a in cfg["areas"]}
    stale = (dt.date.fromisoformat(today) - dt.timedelta(days=45)).isoformat()
    out = [x for x in state["listings"].values()
           if x.get("active") and x.get("area") in areas and x.get("price") is not None
           and x["price"] <= cfg.get("detail_price_max", 112)
           and (not x.get("detail") or x["detail"].get("fetched", "") < stale)]
    rooms = lambda x: sum(int(n) for n in __import__("re").findall(r"\d+", x.get("rooms") or "")) or 0
    out.sort(key=lambda x: (x.get("first_seen", ""), rooms(x) >= 3, (x.get("telek") or 999) >= 400), reverse=True)
    return out


def fetch_details(state: dict, cfg: dict, today: str, cap: int | None = None) -> int:
    """Open each candidate's own page and store condition, m², plot and zártkert hints."""
    cap = cap if cap is not None else cfg.get("detail_max_per_run", 150)
    lo, hi = cfg.get("detail_delay_seconds", [2, 4])
    session = requests.Session()
    done = 0
    for x in detail_candidates(state, cfg, today)[:cap]:
        html = fetch(session, x["url"], tries=2)
        if html is None:
            continue
        d = parse_detail_page(html)
        d["fetched"] = today
        x["detail"] = d
        done += 1
        time.sleep(random.uniform(lo, hi))
    log.info("details fetched: %d", done)
    return done
