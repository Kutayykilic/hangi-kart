"""Akbank (Axess), DenizBank ve Maximum kampanyalarını çekip data/campaigns.json'a yazar.

Kullanım:  python3 scraper/scrape.py
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(Path(__file__).parent))
from extract import enrich  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "campaigns.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def session():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def clean_text(html_or_soup):
    soup = html_or_soup if isinstance(html_or_soup, BeautifulSoup) else BeautifulSoup(html_or_soup, "html.parser")
    for x in soup(["script", "style", "noscript", "svg"]):
        x.decompose()
    txt = soup.get_text("\n", strip=True)
    return re.sub(r"\n{2,}", "\n", txt.replace("\u200b", ""))


# ---------------- Akbank / Axess ----------------
AXESS = "https://www.axess.com.tr"
AXESS_CATS = {
    "397": "Market / Gıda / Restoran", "11422": "Market / Gıda / Restoran",
    "398": "Akaryakıt / Otomotiv", "399": "Giyim / Kozmetik", "405": "Elektronik / İletişim",
    "400": "Ev / Mobilya / Beyaz Eşya", "401": "Seyahat / Turizm", "394": "Online Alışveriş / Eğlence",
    "772": "Online Alışveriş / Eğlence", "403": "Sigorta / Sağlık / Eğitim", "9034": "Sigorta / Sağlık / Eğitim",
    "402": "Yurt dışı", "773": "Nakit", "774": "Diğer",
}


def axess_list(s, cat_id):
    ref = f"{AXESS}/axess/kampanyalar/genel-kampanyalar"
    links, page = [], 1
    while page < 30:
        p = {"checkBox": json.dumps([cat_id]), "searchWord": json.dumps("")}
        if page > 1:
            p["page"] = json.dumps(page)
        r = s.get(f"{AXESS}/ajax/kampanya-ajax.aspx", params=p,
                  headers={"Referer": ref, "X-Requested-With": "XMLHttpRequest"}, timeout=30)
        found = re.findall(r'href="(/axess/kampanyalar/[^"]+)"', r.text)
        if not found:
            break
        links += found
        if r.text.count("grid-3") < 9:
            break
        page += 1
        time.sleep(0.3)
    return list(dict.fromkeys(links))


def axess_detail(s, path):
    r = s.get(AXESS + path, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    h = soup.find("title")
    title = h.get_text(strip=True).replace("| Axess", "").strip() if h else path
    txt = clean_text(soup)
    # Gövde: başlığın ikinci geçtiği yerden "İptal"/footer'a kadar
    i = txt.find(title, txt.find(title) + 1)
    body = txt[i + len(title):] if i > 0 else txt
    body = body.replace("Juzdanı İndir\nSOSYAL MEDYADA PAYLAŞ\n", "")
    for stop in ["\nLimitinizi Artırın", "\nAyın\nKampanyaları", "\nBenzer Kampanyalar", "\nBize Ulaşın"]:
        j = body.find(stop)
        if j > 0:
            body = body[:j]
    img = soup.select_one(".campaingDetailImage img, .detailImage img, img[src*='CmsCampaign']")
    return title, body[:6000], (AXESS + img["src"]) if img and img.get("src", "").startswith("/") else None


def scrape_axess():
    s = session()
    s.get(f"{AXESS}/axess/kampanyalar/genel-kampanyalar", timeout=30)
    path_cats = {}
    for cid, cname in list(AXESS_CATS.items()) + [("0", None)]:
        for p in axess_list(s, cid):
            path_cats.setdefault(p, set())
            if cname:
                path_cats[p].add(cname)
        time.sleep(0.3)
    print(f"  Axess: {len(path_cats)} kampanya linki", file=sys.stderr)

    def one(item):
        path, cats = item
        try:
            title, body, img = axess_detail(s, path)
        except Exception as e:  # noqa: BLE001
            print("  hata", path, e, file=sys.stderr)
            return None
        return {"id": "axess:" + path.rsplit("/", 1)[-1], "bank": "Akbank", "program": "Axess",
                "title": title, "url": AXESS + path, "categories": sorted(cats),
                "text": body, "image": img}

    with ThreadPoolExecutor(4) as ex:
        return [c for c in ex.map(one, path_cats.items()) if c]


# ---------------- Akbank.com (Akbank Mobil, indirim kodları vb.) ----------------
AKBANK = "https://www.akbank.com"


def scrape_akbank():
    s = session()
    soup = BeautifulSoup(s.get(f"{AKBANK}/kampanyalar", timeout=30).text, "html.parser")
    links = {}
    for a in soup.select('a[href^="/kampanyalar/"]'):
        links.setdefault(a["href"].split("?")[0].split("#")[0], a.get_text(" ", strip=True))
    print(f"  Akbank.com: {len(links)} kampanya linki", file=sys.stderr)

    def one(kv):
        path, name = kv
        try:
            r = s.get(AKBANK + path, timeout=30)
            if r.status_code != 200:
                return None
            dsoup = BeautifulSoup(r.text, "html.parser")
            h1 = dsoup.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else name
            main = dsoup.find("main") or dsoup
            txt = clean_text(str(main))
            i = txt.rfind(title)  # sayfa başında tüm kampanyaların listesi var; başlığın son geçişinden sonrası gövde
            body = txt[i + len(title):] if i >= 0 else txt
            body = body.replace("Sayfa İçeriği\n", "")
        except Exception as e:  # noqa: BLE001
            print("  hata", path, e, file=sys.stderr)
            return None
        return {"id": "akbank:" + path.rsplit("/", 1)[-1], "bank": "Akbank", "program": "Akbank",
                "title": title, "url": AKBANK + path, "categories": [], "text": body[:6000], "image": None}

    with ThreadPoolExecutor(4) as ex:
        return [c for c in ex.map(one, links.items()) if c]


# ---------------- Wings (Akbank) ----------------
WINGS = "https://www.wingscard.com.tr"


def scrape_wings():
    s = session()
    h = {"Content-Type": "application/json"}
    items, page = {}, 1
    while page < 60:
        d = s.get(f"{WINGS}/api/campaign/list", params={"keyword": "", "sector": "", "category": "", "page": page},
                  headers=h, timeout=30).json().get("data", {})
        lst = d.get("list", [])
        if not lst:
            break
        for x in lst:
            items[x["url"]] = x
        page += 1
        time.sleep(0.2)
    print(f"  Wings: {len(items)} kampanya", file=sys.stderr)

    def one(x):
        try:
            p = s.get(f"{WINGS}/api/page", params={"url": x["url"].lstrip("/")}, headers=h, timeout=30).json()
            det = next((c["data"] for c in p.get("data", []) if c.get("componentname") == "campaign_detail"), {})
            body = clean_text((det.get("banner_spot") or "") + "\n" + (det.get("detail_content") or ""))
        except Exception as e:  # noqa: BLE001
            print("  hata", x["url"], e, file=sys.stderr)
            body = ""
        title = BeautifulSoup(x["title"], "html.parser").get_text(" ", strip=True)
        return {"id": f"wings:{x['id']}", "bank": "Akbank", "program": "Wings", "title": title,
                "url": WINGS + x["url"], "categories": [x["sector"]] if x.get("sector") else [],
                "text": body[:6000], "start": (x.get("startDate") or "")[:10] or None,
                "end": (x.get("endDate") or "")[:10] or None, "image": x.get("list_image"),
                "note": "Sadece Wings kartlarda geçerli"}

    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(one, items.values()))


# ---------------- QNB (qnbcard.com.tr) ----------------
QNB = "https://www.qnbcard.com.tr"


def scrape_qnb():
    s = session()
    h = {"Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest",
         "Referer": f"{QNB}/kampanyalar"}
    items, page, total = {}, 1, None
    while page < 40:
        d = s.get(f"{QNB}/api/Campaigns", params={"isArchived": "false"},
                  headers={**h, "Page": str(page)}, timeout=30).json()
        total = d.get("TotalItems", 0)
        for x in d.get("Items", []):
            items[x["Id"]] = x
        if not d.get("Items") or len(items) >= total:
            break
        page += 1
        time.sleep(0.3)
    print(f"  QNB: {len(items)}/{total} kampanya", file=sys.stderr)
    out = []
    for x in items.values():
        seo = (x.get("SeoProperty") or {}).get("Name") or ""
        out.append({"id": f"qnb:{x['Id']}", "bank": "QNB", "program": "QNB",
                    "title": BeautifulSoup(x["Title"], "html.parser").get_text(" ", strip=True),
                    "url": f"{QNB}/kampanyalar/{seo}",
                    "categories": [], "text": clean_text(x.get("Content") or "")[:6000], "image": None})
    return out


# ---------------- DenizBank ----------------
DENIZ = "https://www.denizbank.com"


def ddmmyyyy(s):
    try:
        return datetime.strptime(s[:10], "%d/%m/%Y").date().isoformat()
    except Exception:  # noqa: BLE001
        return None


def scrape_denizbank():
    s = session()
    out = []
    for cat_id, cat_name in [("213", "Kart Kampanyaları"), ("392", "MobilDeniz Fırsatları"), ("395", "Diğer")]:
        r = s.get(f"{DENIZ}/api/campaign/search", params={"key": "", "categoryId": cat_id},
                  headers={"Accept": "application/json", "X-Bone-Language": "TR"}, timeout=30)
        for x in r.json():
            out.append({"id": f"deniz:{x['Id']}", "bank": "DenizBank", "program": "DenizBank",
                        "title": x["Title"], "url": DENIZ + x["CampaignUrl"], "categories": [cat_name],
                        "text": (x.get("ShortDescription") or "") + "\n" + clean_text(x.get("Content") or ""),
                        "start": ddmmyyyy(x.get("StartDate", "")), "end": ddmmyyyy(x.get("EndDate", "")),
                        "image": None})
    print(f"  DenizBank: {len(out)} kampanya", file=sys.stderr)
    return list({c["id"]: c for c in out}.values())


# ---------------- Maximum (DenizBank 6 Aralık 2026'da geçiyor) ----------------
MAXIMUM = "https://www.maximum.com.tr"


def scrape_maximum():
    s = session()
    t = s.get(f"{MAXIMUM}/kampanyalar", timeout=60).text
    items = {}
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        try:
            ld = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            continue
        stack = [ld]
        while stack:  # JSON-LD ağacında "Offer" tipindeki kampanyaları bul
            x = stack.pop()
            if isinstance(x, list):
                stack += x
            elif isinstance(x, dict):
                if x.get("@type") == "Offer" and "/kampanyalar/" in x.get("url", ""):
                    items[x["url"].split("#")[0]] = x.get("name", "")
                stack += list(x.values())
    print(f"  Maximum: {len(items)} kampanya", file=sys.stderr)

    def one(kv):
        url, name = kv
        try:
            txt = clean_text(s.get(url, timeout=60).text)
        except Exception as e:  # noqa: BLE001
            print("  hata", url, e, file=sys.stderr)
            return None
        i = txt.find("KAMPANYA TARİHLERİ")
        body = txt[i:] if i >= 0 else txt
        j = body.find("Ek Koşullar")
        if j > 0:  # sayfa geçmiş dönemleri de içeriyor, ilk dönemin sonunda kes
            k = body.find("\n", body.find("\n", j) + 1)
            body = body[: k if k > 0 else j]
        body = body.replace("KAMPANYA TARİHLERİ\n:\n", "Kampanya tarihleri: ").replace("\n-\n", " - ")
        note = ("DenizBank kartları da dahil" if "denizbank" in body.lower() else
                "DenizBank kartları 6 Aralık 2026'da Maximum'a geçiyor; kampanyanın DenizBank kartlarını kapsayıp kapsamadığını kontrol et")
        return {"id": "max:" + url.rstrip("/").rsplit("/", 1)[-1], "bank": "DenizBank", "program": "Maximum",
                "title": name, "url": url, "categories": [], "text": body[:6000], "image": None, "note": note}

    with ThreadPoolExecutor(4) as ex:
        return [c for c in ex.map(one, items.items()) if c]


def main():
    all_c = []
    sources = [("Axess", scrape_axess), ("Akbank.com", scrape_akbank), ("Wings", scrape_wings),
               ("QNB", scrape_qnb), ("DenizBank", scrape_denizbank), ("Maximum", scrape_maximum)]
    for name, fn in sources:
        print(f"{name} çekiliyor...", file=sys.stderr)
        try:
            all_c += fn()
        except Exception as e:  # noqa: BLE001
            print(f"  {name} başarısız: {e}", file=sys.stderr)
    today = date.today().isoformat()
    result = []
    for c in all_c:
        enrich(c)
        if c.get("end") and c["end"] < today:
            continue
        result.append(c)
    # Kaynakların çoğu başarısız olduysa (ör. IP engeli) eski veriyi koru
    if len(result) < 100:
        print(f"Sadece {len(result)} kampanya geldi; mevcut veri korunuyor.", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.now().isoformat(timespec="minutes"),
                               "campaigns": result}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(result)} aktif kampanya -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
