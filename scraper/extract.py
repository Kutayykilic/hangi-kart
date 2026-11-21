"""Kampanya metninden yapılandırılmış alanlar çıkaran sezgisel (regex) ayrıştırıcı."""
import re
from datetime import date

AYLAR = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
}
AY_RE = "|".join(AYLAR)
NUM = r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+"
REWARD_WORDS = r"(chip-?para|maxipuan|parapuan|mil\s?puan|bonus|indirim|iade|puan|nakit|hediye)"


def to_num(s):
    return float(s.replace(".", "").replace(",", "."))


def parse_dates(text):
    """Metindeki ilk tarih aralığını bulur (farklı yazım biçimleri arasından en erken geçen)."""
    t = text.lower()
    cands = []
    m = re.search(rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+({AY_RE})\s+(\d{{4}})", t)
    if m:  # 1-30 Kasım 2026
        y, ay = int(m[4]), AYLAR[m[3]]
        cands.append((m.start(), _d(y, ay, int(m[1])), _d(y, ay, int(m[2]))))
    m = re.search(rf"(\d{{1,2}})\s+({AY_RE})(?:\s+(\d{{4}}))?\s*[-–]\s*(\d{{1,2}})\s+({AY_RE})\s+(\d{{4}})", t)
    if m:  # 1 Temmuz – 31 Aralık 2026
        y2, a1, a2 = int(m[6]), AYLAR[m[2]], AYLAR[m[5]]
        y1 = int(m[3]) if m[3] else (y2 if a1 <= a2 else y2 - 1)
        cands.append((m.start(), _d(y1, a1, int(m[1])), _d(y2, a2, int(m[4]))))
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})\s*(?:\d{1,2}:\d{2})?\s*[-–]\s*(\d{1,2})[./](\d{1,2})[./](\d{4})", t)
    if m:  # 01.11.2026 - 30.11.2026
        cands.append((m.start(), _d(int(m[3]), int(m[2]), int(m[1])), _d(int(m[6]), int(m[5]), int(m[4]))))
    m = re.search(rf"(\d{{1,2}})\s+({AY_RE})\s+(\d{{4}})['’]?\w*\s+(?:tarihine\s+)?kadar", t)
    if m:  # 30 Kasım 2026'ya kadar
        cands.append((m.start(), None, _d(int(m[3]), AYLAR[m[2]], int(m[1]))))
    if not cands:
        return None, None
    _, a, b = min(cands)
    return a, b


def _d(y, m, d):
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_reward(title, text):
    """Kazanç türünü ve miktarını çıkarır."""
    head = f"{title}. {text[:600]}"
    low = head.lower()
    r = {"kind": None, "amount": None, "percent": None, "cap": None,
         "per_spend": None, "per_reward": None, "installments": None}

    m = re.search(r"(?:%\s?(\d{1,2})|(\d{1,2})\s?%)\s*(?:'?(?:ye|ya|e|a)\s+varan\s+)?(indirim|iade|chip-?para|maxipuan|parapuan|bonus)", low)
    if m:
        r["percent"] = int(m[1] or m[2])
        r["kind"] = m[3]
    # her 2.750 TL ... 100 TL
    m = re.search(rf"her\s+({NUM})\s*tl[^.]{{0,80}}?\b({NUM})\s*(?:tl\b|,)", low)
    if m:
        r["per_spend"], r["per_reward"] = to_num(m[1]), to_num(m[2])
    m = re.search(rf"toplamda\s+({NUM})\s*tl", low) or re.search(rf"({NUM})\s*tl'?(?:ye|ya)\s+varan", low)
    if m:
        r["cap"] = to_num(m[1])
    m = re.search(rf"({NUM})\s*tl'?(?:ye|ya)?\s*(?:varan\s+)?{REWARD_WORDS}", low)
    if m:
        r["amount"] = to_num(m[1])
        r["kind"] = r["kind"] or m[2]
    m = re.search(r"(\d{1,2})\s*(?:aya\s+varan\s+|ay\s+)?(?:ek\s+)?taksit", low)
    if m and int(m[1]) > 1:
        r["installments"] = int(m[1])
        if not r["kind"]:
            r["kind"] = "taksit"
    if r["kind"]:
        r["kind"] = r["kind"].replace("chippara", "chip-para")
    return r


def parse_min_spend(text):
    for m in re.finditer(rf"({NUM})\s*TL\s*(?:ve|veya)\s*üzeri", text, re.I):
        ctx = text[max(0, m.start() - 60):m.start()].lower()
        if to_num(m[1]) < 1_000_000 and "birikim" not in ctx and "mevduat" not in ctx:
            return to_num(m[1])
    # "10.000 TL'ye 2.500 TL indirim"
    m = re.search(rf"({NUM})\s*TL['’]?(?:ye|ya)\s+({NUM})\s*TL", text, re.I)
    if m and to_num(m[1]) > to_num(m[2]):
        return to_num(m[1])
    return None


def parse_join(text):
    m = re.search(r"[\"“”']([A-ZÇĞİÖŞÜ0-9]{2,20})[\"“”']\s*yaz[ıi]p\s*(\d{4})", text)
    if m:
        return f"SMS: \"{m[1]}\" yazıp {m[2]}'ya gönder"
    low = text.lower()
    if "hemen katıl" in low or ("juzdan" in low and "kaydol" in low):
        return "Juzdan'dan \"Hemen Katıl\""
    m = re.search(r"([A-ZÇĞİÖŞÜ0-9]{2,20})\s*(?:yaz[ıi]p|yazarak)\s*(\d{4})", text)
    if m:
        return f"SMS: \"{m[1]}\" yazıp {m[2]}'ya gönder"
    if "qnb mobil" in low and "katıl" in low:
        return "QNB Mobil'den katıl"
    if "akbank mobil" in low and re.search(r"kod", low):
        return "İndirim kodunu Akbank Mobil'den al, ödemede gir"
    if "işcep" in low and "katıl" in low:
        return "İşCep / Maximum Mobil'den katıl"
    if ("denizkart" in low or "mobildeniz" in low) and "kampanyaya katıl" in low:
        return "MobilDeniz / DenizKartım'dan katıl"
    if re.search(r"katıl[ıi]m\s+gerek(?:mez|memektedir)|otomatik\s+olarak", low):
        return "Otomatik (katılım gerekmez)"
    if "katıl" in low:
        return "Katılım gerekli – detaya bak"
    return None


def parse_code(text):
    m = re.search(r"\b([A-Z][A-Z0-9]{3,19})\s+(?:indirim\s+|kupon\s+|promosyon\s+)?kod", text)
    if m and m[1] not in {"SMS", "TROY", "AVM", "ATM", "POS"}:
        return m[1]
    m = re.search(r"(?:kod|kupon)[^.\n]{0,60}?[\"“'”]?\b([A-Z][A-Z0-9]{3,19})\b", text)
    if m and m[1] not in {"SMS", "TL", "TROY", "QR", "AVM", "ATM", "POS"}:
        return m[1]
    return None


def enrich(c):
    text = c.get("text", "")
    start, end = parse_dates(text)
    c["start"], c["end"] = c.get("start") or start, c.get("end") or end
    c["reward"] = parse_reward(c["title"], text)
    c["min_spend"] = parse_min_spend(text)
    c["join"] = parse_join(text)
    c["code"] = parse_code(text)
    return c
