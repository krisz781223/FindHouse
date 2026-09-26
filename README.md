# FindHouse

Saját házkereső: minden nap letölti a koltozzbe.hu családiház-hirdetéseit a beállított településekről és kerületekből, összevonja az ugyanarra a házra feltett hirdetéseket, jelzi a gyanús vagy kockázatos hirdetéseket, és egy szűrhető weboldalt készít belőlük.

## Mit tud

- **Területek és ársáv:** a `config.json`-ban állíthatók. Most 6 település (Göd, Veresegyház, Pomáz, Szentendre, Fót, Csömör) és 6 kerület (XIV., XV., XVI., II., XII., III.), 50–130 millió Ft között.
- **Összevonás:** ha ugyanazt a házat több iroda hirdeti (egyezik a terület, a szobaszám, az m², a telek és az építési év), egy sorba kerül, a legalacsonyabb árral.
- **Jelzések:**
  - új hirdetés (az utolsó 3 napban jelent meg)
  - árcsökkenés
  - gyanús szobaszám (kevesebb mint 22 m² jut egy szobára)
  - új vagy épülő ház
  - üdülőövezet
  - régi építés
  - kis telek
- **Előzmények:** a `data/state.json` minden hirdetés árváltozását és első megjelenését megőrzi. A megszűnt hirdetések inaktívak lesznek, de nem törlődnek.
- **Utazási idők:** település- vagy kerületszintű becslések a `config.json`-ban (tömegközlekedéssel a Csalogány utcáig, autóval a munkahelyig). Nem útvonaltervezőből jönnek.

## Futtatás a saját gépen

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m findhouse --area "Göd"   # próbafutás egy területtel
python -m findhouse                # minden terület (kb. 10–15 perc, szándékosan lassú)
```

Az eredmény a `docs/index.html`, ezt böngészőben meg tudod nyitni. A `python -m findhouse --build` letöltés nélkül, csak a meglévő adatokból építi újra az oldalt.

## Automatikus napi futás (GitHub Actions és Pages)

1. **Actions engedélyezése:** a repóban nyisd meg a *Settings → Actions → General* oldalt, és a *Workflow permissions* résznél válaszd a **Read and write permissions** beállítást.
2. **Pages bekapcsolása:** *Settings → Pages → Source: Deploy from a branch*, a Branch legyen `main`, a mappa `/docs`. Pár perc múlva az oldal elérhető a `https://krisz781223.github.io/findhouse/` címen.
3. **Első futás:** az *Actions* fülön nyisd meg a *Napi házkeresés* workflow-t, és indítsd el a **Run workflow** gombbal. Utána minden reggel magától fut.

Ha a futás napló „HTTP 403” vagy „Nothing scraped” hibát ír, a hirdetési oldal valószínűleg letiltja a GitHub szervereiről érkező kéréseket. Ilyenkor futtasd a saját gépedről (vagy egy Azure-ban futó időzített feladatból), és pushold fel az eredményt.

## Szerkezet

| Útvonal | Mi van benne |
|---|---|
| `findhouse/parse.py` | a listaoldalak értelmezése (tesztelve: `tests/`) |
| `findhouse/scrape.py` | letöltés, oldalanként 3–6 mp szünettel |
| `findhouse/pipeline.py` | előzmények frissítése, összevonás, jelzések, oldalépítés |
| `site/template.html` | a weboldal sablonja |
| `data/state.json` | az összes valaha látott hirdetés, árelőzménnyel |
| `docs/` | a kész oldal (ezt szolgálja ki a GitHub Pages) |

## Fair use

A program csak saját célra, naponta egyszer, lassan kér le nyilvános listaoldalakat. Ne sűrítsd a futást, és ne használd az adatokat kereskedelmi célra.

## Ismert korlát

A letöltő a koltozzbe.hu oldal szerkezetére épül. Az értelmező a hirdetési linkek szövegét olvassa, nem a CSS-osztályokat, ezért elég stabil, de ha az oldal jelentősen megváltozik, a `parse.py`-t igazítani kell. A kódot nem tudtam élesben a koltozzbe.hu-n tesztelni, ezért az első futást érdemes egy területtel (`--area`) megnézni.
