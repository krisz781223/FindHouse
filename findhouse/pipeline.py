"""Merge a scrape into the running state, compute flags, and build the site."""
from __future__ import annotations
import json, re, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
SITE_TEMPLATE = ROOT / "site" / "template.html"
SITE_OUT = ROOT / "docs" / "index.html"


def load_state() -> dict:
    return json.loads(STATE.read_text("utf-8")) if STATE.exists() else {"listings": {}, "runs": []}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")


def update_state(state: dict, rows: list[dict], report: dict, today: str) -> dict:
    """Upsert scraped cards. Listings not seen today are marked inactive (kept for history)."""
    L = state["listings"]
    seen_today = set()
    for r in rows:
        if r.get("price") is None:
            continue
        key = r["url"]
        seen_today.add(key)
        cur = L.get(key)
        if cur is None:
            L[key] = {**r, "first_seen": today, "last_seen": today, "active": True,
                      "price_history": [[today, r["price"]]]}
        else:
            if cur["price_history"][-1][1] != r["price"]:
                cur["price_history"].append([today, r["price"]])
            for k in ("price", "rooms", "m2", "telek", "year", "area"):
                if r.get(k) is not None:
                    cur[k] = r[k]
            if r.get("note"):
                cur["note"] = r["note"]
            cur["last_seen"] = today
            cur["active"] = True
    # only deactivate listings in areas that were scraped without failures
    clean_areas = {a for a, s in report.items() if not s["failed"]}
    for key, cur in L.items():
        if key not in seen_today and cur.get("area") in clean_areas:
            cur["active"] = False
    state["runs"].append({"date": today, "report": report})
    state["runs"] = state["runs"][-60:]
    return state


def _flags(rooms, m2, telek, year, note):
    rsum = sum(int(x) for x in re.findall(r"\d+", rooms)) if rooms else None
    f, n = [], (note or "").lower()
    if m2 and rsum and m2 / rsum < 22: f.append("gyanús szobaszám")
    if (year and year >= 2025) or any(k in n for k in ("építkeznél", "új építésű", "újépítésű")): f.append("új / épülő")
    if any(k in n for k in ("hétvégi", "üdülő", "nyaraló", "zártkert")): f.append("üdülőövezet")
    if year and year < 1980: f.append("régi építés")
    if "felújítandó" in n: f.append("felújítandó")
    if m2 is None: f.append("hiányzó m²")
    if telek is not None and telek < 400: f.append("kis telek")
    if any(k in n for k in ("műhely", "üzlet", "befektet")): f.append("nem tipikus családi ház")
    return rsum, f


def build_rows(state: dict, cfg: dict, today: str) -> list[dict]:
    areas = {a["name"]: a for a in cfg["areas"]}
    lo, hi = cfg["price_min"], cfg["price_max"]
    new_after = (dt.date.fromisoformat(today) - dt.timedelta(days=cfg["new_days"])).isoformat()
    active = [x for x in state["listings"].values() if x.get("active") and x.get("area") in areas]
    groups = defaultdict(list)  # same house listed by several agencies
    for x in active:
        groups[(x["area"], x.get("rooms"), x.get("m2"), x.get("telek"), x.get("year"))].append(x)
    out = []
    for g in groups.values():
        g.sort(key=lambda x: x["price"])
        m = g[0]
        if not (lo <= m["price"] <= hi):
            continue
        a = areas[m["area"]]
        rsum, flags = _flags(m.get("rooms"), m.get("m2"), m.get("telek"), m.get("year"), m.get("note"))
        first_seen = min(x["first_seen"] for x in g)
        if first_seen > new_after:
            flags.insert(0, "új hirdetés")
        hist = m["price_history"]
        if len(hist) > 1 and hist[-1][1] < max(p for _, p in hist):
            flags.insert(0, "árcsökkenés")
        bkv = list(a["bkv"])
        if m["area"] == "Szentendre":
            n = (m.get("note") or "").lower()
            ov = cfg["szentendre_bkv_overrides"]
            if "hév" in n: bkv = ov["near_hev"]
            elif any(k in n for k in ("pismány", "boldogtanya", "tyúkosdűlő", "petyina")): bkv = ov["hills"]
        out.append(dict(
            town=m["area"], price=m["price"], rooms=m.get("rooms"), rsum=rsum, m2=m.get("m2"),
            telek=m.get("telek"), year=m.get("year"),
            ppm=round(m["price"] * 1e6 / m["m2"]) if m.get("m2") else None,
            note=m.get("note") or "", flags=flags, n=len(g),
            others=sorted({x["price"] for x in g[1:] if x["price"] != m["price"]}),
            transit=a["transit"], url=m["url"], dupurls=[x["url"] for x in g[1:]],
            bkv=bkv, car=list(a["car"]), first_seen=first_seen))
    return out


def build_site(rows: list[dict], cfg: dict, today: str) -> None:
    t = SITE_TEMPLATE.read_text("utf-8")
    t = t.replace("__DATA__", json.dumps(rows, ensure_ascii=False))
    t = t.replace("__TOWNS__", json.dumps([a["name"] for a in cfg["areas"]], ensure_ascii=False))
    t = t.replace("__DATE__", today).replace("__PMIN__", str(cfg["price_min"])).replace("__PMAX__", str(cfg["price_max"]))
    SITE_OUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUT.write_text(t, "utf-8")
    (SITE_OUT.parent / "data.json").write_text(json.dumps(rows, ensure_ascii=False), "utf-8")
