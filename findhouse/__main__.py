"""Usage:
  python -m findhouse            # scrape all areas, update state, rebuild the site
  python -m findhouse --build    # only rebuild the site from data/state.json
  python -m findhouse --artifact OUT.html   # same page for Claude (shared marks when served there)
"""
import argparse, json, logging, datetime as dt
from pathlib import Path
from . import pipeline

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="rebuild site only, no scraping")
    ap.add_argument("--area", help="scrape only this area name (for testing)")
    ap.add_argument("--artifact", metavar="OUT", help="build the shared-marks page from the current data only")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = json.loads((pipeline.ROOT / "config.json").read_text("utf-8"))
    today = dt.date.today().isoformat()
    state = pipeline.load_state()
    if args.build or args.artifact:
        # a legutóbbi futás napja számít "mának"
        runs = [r["date"] for r in state.get("runs", []) if isinstance(r.get("report"), dict)]
        today = runs[-1] if runs else today
    if args.artifact:
        rows = pipeline.build_rows(state, cfg, today)
        pipeline.build_site(rows, cfg, today, out=Path(args.artifact), data_json=False)
        logging.info("artifact page built with %d houses -> %s", len(rows), args.artifact)
        return
    if not (args.build or args.artifact):
        from .scrape import scrape_all
        if args.area:
            cfg = {**cfg, "areas": [a for a in cfg["areas"] if a["name"] == args.area]}
        rows, report = scrape_all(cfg)
        if not rows:
            raise SystemExit("Nothing scraped – the site may have changed or blocked the request. State left untouched.")
        state = pipeline.update_state(state, rows, report, today)
        pipeline.save_state(state)
        cfg = json.loads((pipeline.ROOT / "config.json").read_text("utf-8"))
    rows = pipeline.build_rows(state, cfg, today)
    pipeline.build_site(rows, cfg, today)
    logging.info("site built with %d houses", len(rows))

if __name__ == "__main__":
    main()
