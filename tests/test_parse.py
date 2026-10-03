from findhouse.parse import parse_card_text, parse_list_page

def test_full_card():
    t = ("Eladó családi ház, Pomázon 98.5 M Ft, 4 szobás 98.5 M Ft 684 028 Ft/m2 Pomáz - Eladó családi ház "
         "Eladó Pomázon, csendes kertvárosi övezetben, egy bruttó 144 nm-es 3 szintes ... "
         "4 szoba144 m2telekméret:748 m² építés éve:1995")
    r = parse_card_text(t)
    assert r["price"] == 98.5 and r["rooms"] == "4" and r["m2"] == 144 and r["telek"] == 748 and r["year"] == 1995
    assert r["note"].startswith("Eladó Pomázon")

def test_plus_rooms_and_hectare():
    t = "199 M Ft 818 930 Ft/m2 Pomáz - Eladó családi ház Panoráma ... 5 + 2 szoba243 m2telekméret:1 ha építés éve:2023"
    r = parse_card_text(t)
    assert r["rooms"] == "5+2" and r["m2"] == 243 and r["telek"] == 10000 and r["year"] == 2023

def test_missing_m2_and_year():
    t = "59 M Ft 48 007 Ft/m2 Pomáz - Eladó családi ház Fiatal felnőttek ... 2 szoba telekméret:1229 m²"
    r = parse_card_text(t)
    assert r["price"] == 59 and r["m2"] is None and r["telek"] == 1229 and r["year"] is None

def test_list_page_links_and_pagination():
    html = '''<a href="/elado-csaladi_haz-god/h10902470">105 M Ft 1 000 000 Ft/m2 Göd - Eladó családi ház Felső-Göd ...
              4 szoba105 m2telekméret:1137 m² építés éve:1970</a>
              <a href="/elado-csaladi_haz-god?page=2">2</a><a href="/elado-csaladi_haz-god?page=8">8</a>
              <a href="/elado-csaladi_haz-fot/h1">99 M Ft</a>'''
    items, last = parse_list_page(html, "god")
    assert last == 8 and len(items) == 1
    assert items[0]["url"].endswith("/h10902470") and items[0]["m2"] == 105


def test_pipeline_new_and_price_drop():
    from findhouse import pipeline
    cfg = {"price_min": 50, "price_max": 130, "new_days": 3,
           "areas": [{"name": "Göd", "slug": "god", "transit": "x", "bkv": [1, 2], "car": [3, 4]}],
           "szentendre_bkv_overrides": {"near_hev": [0, 0], "hills": [0, 0]}}
    st = {"listings": {}, "runs": []}
    a = {"url": "u1", "id": "h1", "area": "Göd", "price": 100, "rooms": "4", "m2": 120, "telek": 800, "year": 1999, "note": ""}
    rep = {"Göd": {"failed": []}}
    pipeline.update_state(st, [a], rep, "2026-09-01")
    pipeline.update_state(st, [{**a, "price": 95}], rep, "2026-09-20")
    rows = pipeline.build_rows(st, cfg, "2026-09-20")
    assert rows[0]["price"] == 95 and "árcsökkenés" in rows[0]["flags"] and "új hirdetés" not in rows[0]["flags"]
    pipeline.update_state(st, [], rep, "2026-09-21")   # listing disappeared
    assert pipeline.build_rows(st, cfg, "2026-09-21") == []


def _cfg():
    return {"price_min": 50, "price_max": 130, "new_days": 3,
            "areas": [{"name": "Göd", "slug": "god", "transit": "x", "bkv": [1, 2], "car": [3, 4]}],
            "szentendre_bkv_overrides": {"near_hev": [0, 0], "hills": [0, 0]}}


def test_baseline_new_and_relisted():
    from findhouse import pipeline
    rep = {"Göd": {"failed": []}}
    a = {"url": "u1", "id": "h1", "area": "Göd", "price": 100, "rooms": "4", "m2": 120, "telek": 800, "year": 1999, "note": ""}
    b = {"url": "u2", "id": "h2", "area": "Göd", "price": 90, "rooms": "3", "m2": 95, "telek": 600, "year": 1985, "note": ""}
    st = {"listings": {}, "runs": []}
    pipeline.update_state(st, [a], rep, "2026-10-02")          # first full run = baseline
    rows = pipeline.build_rows(st, _cfg(), "2026-10-02")
    assert rows[0]["status"] == "" and "új hirdetés" not in rows[0]["flags"]
    pipeline.update_state(st, [a, b], rep, "2026-10-03")        # b is genuinely new
    rows = {r["url"]: r for r in pipeline.build_rows(st, _cfg(), "2026-10-03")}
    assert rows["u2"]["status"] == "new" and rows["u2"]["today"] and "új hirdetés" in rows["u2"]["flags"]
    pipeline.update_state(st, [b], rep, "2026-10-04")           # a disappears
    pipeline.update_state(st, [b, {**a, "url": "u3", "id": "h3", "price": 97}], rep, "2026-10-08")  # same house, new ad
    rows = {r["url"]: r for r in pipeline.build_rows(st, _cfg(), "2026-10-08")}
    r = rows["u3"]
    assert r["status"] == "relisted" and "újra feltéve" in r["flags"] and "új hirdetés" not in r["flags"]
    assert r["orig_first"] == "2026-10-02" and r["orig_price"] == 100 and "árcsökkenés" in r["flags"]
    assert rows["u2"]["status"] == ""                           # older than 3 days


def test_same_url_reappears():
    from findhouse import pipeline
    rep = {"Göd": {"failed": []}}
    a = {"url": "u1", "id": "h1", "area": "Göd", "price": 100, "rooms": "4", "m2": 120, "telek": 800, "year": 1999, "note": ""}
    st = {"listings": {}, "runs": []}
    pipeline.update_state(st, [a], rep, "2026-10-02")
    pipeline.update_state(st, [], rep, "2026-10-05")
    pipeline.update_state(st, [a], rep, "2026-10-09")
    r = pipeline.build_rows(st, _cfg(), "2026-10-09")[0]
    assert r["status"] == "relisted" and r["today"]
