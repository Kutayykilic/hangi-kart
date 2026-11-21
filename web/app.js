// Hangi Kart? — istemci tarafı eşleştirme ve kazanç tahmini

const CATEGORIES = {
  market:     { label: "🛒 Market",     axess: "Market / Gıda / Restoran", kw: ["market", "gida", "migros", "a101", "bim", "sok", "carrefour", "carrefoursa", "macrocenter", "metro", "file", "onur", "bizimtoptan", "getir", "istegelsin", "manav", "kasap"] },
  restoran:   { label: "🍽️ Restoran",   axess: "Market / Gıda / Restoran", kw: ["restoran", "yemek", "kafe", "cafe", "kahve", "starbucks", "yemeksepeti", "burger", "pizza", "dominos", "trendyol yemek", "migros yemek"] },
  akaryakit:  { label: "⛽ Akaryakıt",  axess: "Akaryakıt / Otomotiv", kw: ["akaryakit", "benzin", "mazot", "motorin", "yakit", "shell", "opet", "bp", "petrol ofisi", "po", "total", "aytemiz", "otomotiv", "lastik", "arac", "otopark", "servis"] },
  giyim:      { label: "👕 Giyim",      axess: "Giyim / Kozmetik", kw: ["giyim", "kiyafet", "ayakkabi", "zara", "mavi", "lcw", "lc waikiki", "koton", "defacto", "boyner", "bershka", "oysho", "pull&bear", "h&m", "kozmetik", "gratis", "watsons", "sephora", "parfum", "aksesuar", "canta"] },
  elektronik: { label: "📱 Elektronik", axess: "Elektronik / İletişim", kw: ["elektronik", "telefon", "iphone", "samsung", "apple", "bilgisayar", "laptop", "tablet", "mediamarkt", "teknosa", "vatan", "turkcell", "vodafone", "turk telekom", "fatura"] },
  ev:         { label: "🛋️ Ev & Mobilya", axess: "Ev / Mobilya / Beyaz Eşya", kw: ["mobilya", "beyaz esya", "ev", "ikea", "koctas", "bauhaus", "madame coco", "english home", "karaca", "arcelik", "bosch", "vestel", "beko", "yapi market", "dekorasyon"] },
  seyahat:    { label: "✈️ Seyahat",    axess: "Seyahat / Turizm", kw: ["seyahat", "ucak", "bilet", "otobus bileti", "bilet.com", "otel", "tatil", "thy", "pegasus", "ajet", "anadolujet", "turizm", "araba kiralama", "rent", "obilet", "enuygun", "etstur", "jolly", "otobus", "havalimani"] },
  online:     { label: "🛍️ Online",     axess: "Online Alışveriş / Eğlence", kw: ["online", "internet", "e-ticaret", "trendyol", "hepsiburada", "amazon", "n11", "pazarama", "pttavm", "ciceksepeti", "netflix", "spotify", "youtube", "disney", "oyun", "steam", "sinema", "konser", "passo", "biletix"] },
  saglik:     { label: "🏥 Sağlık & Eğitim", axess: "Sigorta / Sağlık / Eğitim", kw: ["saglik", "hastane", "eczane", "sigorta", "egitim", "okul", "kurs", "universite", "kitap", "kirtasiye", "dis"] },
  yurtdisi:   { label: "🌍 Yurt dışı",  axess: "Yurt dışı", kw: ["yurt disi", "yurtdisi", "abroad", "doviz"] },
};

const STOP = new Set(("tl lira ₺ alisveris alisverisi harcama harcamasi yapacagim yapcam alacagim almak alicam odeme odeyecegim icin ile ve bir de da te ta su bu " +
  "lik luk kadar civari yaklasik toplam magaza magazasi magazasinda kart kredi").split(" "));

let DATA = [];
const $ = (s) => document.querySelector(s);

function norm(s) {
  return (s || "").toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/ı/g, "i").replace(/[’'`]/g, "'");
}
const fmt = (n) => n == null ? "" : n.toLocaleString("tr-TR", { maximumFractionDigits: 0 });

// Basit Türkçe ek kırpma: "bileti" -> "bilet", "otellerde" -> "otel"
const SUFFIXES = ["lerinde", "larinda", "lerde", "larda", "leri", "lari", "inde", "inda", "nde", "nda", "ler", "lar", "den", "dan", "ten", "tan", "si", "su", "de", "da", "te", "ta", "i", "u"];
function stem(w) {
  if (STOP.has(w)) return w;
  for (const suf of SUFFIXES) {
    if (w.length - suf.length >= 4 && w.endsWith(suf)) return w.slice(0, -suf.length);
  }
  return w;
}

function parseQuery(q) {
  const n = norm(q);
  let amount = null;
  const m = n.match(/(\d{1,3}(?:[.,]\d{3})+|\d+)(?:\s*(?:k|bin))?\s*(?:tl|₺|lira)?/g);
  if (m) {
    for (const raw of m) {
      let v = parseFloat(raw.replace(/[.,](?=\d{3}\b)/g, "").replace(/[^\d.]/g, ""));
      if (/\b(k|bin)\b|\dk\b/.test(raw)) v *= 1000;
      if (v >= 10 && (amount == null || v > amount)) amount = v;
    }
  }
  const words = n.replace(/\d+([.,]\d+)*/g, " ").split(/[^a-z0-9&']+/)
    .map((w) => stem(w.split("'")[0])).filter((w) => w.length >= 2 && !STOP.has(w));
  const cats = new Set();
  for (const [key, c] of Object.entries(CATEGORIES)) {
    for (const kw of c.kw) {
      if (kw.includes(" ") ? n.includes(kw) : words.some((w) => w === kw || (w.length >= 4 && kw.length >= 4 && (w.startsWith(kw) || kw.startsWith(w))))) {
        cats.add(key);
      }
    }
  }
  return { amount, words, cats };
}

// Bir kelime kampanya metninde geçiyor mu? (Türkçe ekleri tolere eder: "migros'ta" -> "migros")
function hits(word, hay) {
  if (word.length < 3) return new RegExp(`\\b${word}\\b`).test(hay);
  return new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(hay);
}

function score(c, q) {
  let s = 0;
  const t = c._title, x = c._text;
  for (const w of q.words) {
    if (hits(w, t)) s += 10;
    else if (hits(w, x)) s += 3;
  }
  for (const key of q.cats) {
    const cat = CATEGORIES[key];
    if (c.categories.includes(cat.axess)) s += 4;
    if (cat.kw.some((k) => k.length >= 3 && hits(k, t))) s += 5;
  }
  return s;
}

// Harcama tutarına göre tahmini kazanç
function estimate(c, amount) {
  const r = c.reward || {};
  const out = { value: null, label: null, sub: null, eligible: true };
  if (amount != null && c.min_spend && amount < c.min_spend) out.eligible = false;

  if (r.kind === "taksit" && !r.amount && !r.percent) {
    out.label = `${r.installments || ""} taksit`;
    out.sub = "peşin fiyatına";
    return out;
  }
  if (r.percent) {
    out.label = `%${r.percent}`;
    out.sub = r.kind || "indirim";
    if (amount != null) {
      let v = (amount * r.percent) / 100;
      if (r.cap) v = Math.min(v, r.cap);
      out.value = out.eligible ? v : 0;
    }
    return out;
  }
  if (r.per_spend && r.per_reward) {
    out.sub = r.kind || "kazanç";
    if (amount != null) {
      let v = Math.floor(amount / r.per_spend) * r.per_reward;
      if (r.cap) v = Math.min(v, r.cap);
      out.value = v;
      out.eligible = v > 0;
    } else {
      out.label = `${fmt(r.cap || r.amount)} TL'ye kadar`;
    }
    return out;
  }
  if (r.amount) {
    out.sub = r.kind || "kazanç";
    if (amount != null) out.value = out.eligible ? r.amount : 0;
    else out.label = `${fmt(r.amount)} TL`;
    return out;
  }
  out.label = "Fırsat";
  out.sub = "detaya bak";
  return out;
}

function daysLeft(end) {
  if (!end) return null;
  const d = Math.ceil((new Date(end + "T23:59:59") - new Date()) / 86400000);
  return d;
}

function render() {
  const raw = $("#q").value.trim();
  const progs = new Set([...document.querySelectorAll("[data-prog]")].filter((e) => e.checked).map((e) => e.dataset.prog));
  const hideTaksit = $("#hideTaksit").checked;
  const res = $("#results");
  if (!raw) {
    res.innerHTML = `<div class="empty">Yukarıya ne alacağını yaz ya da bir kategori seç.</div>`;
    $("#summary").textContent = "";
    return;
  }
  const q = parseQuery(raw);
  let list = DATA.filter((c) => progs.has(c.program))
    .map((c) => ({ c, s: score(c, q), e: estimate(c, q.amount) }))
    .filter((r) => r.s > 0)
    .filter((r) => !(hideTaksit && r.c.reward?.kind === "taksit" && !r.c.reward.amount && !r.c.reward.percent));
  const max = Math.max(0, ...list.map((r) => r.s));
  list = list.filter((r) => r.s >= max * 0.45);
  // Önce alaka katmanı (marka/başlık eşleşmesi güçlü olanlar), sonra uygunluk, sonra tahmini kazanç
  const tier = (r) => (r.s >= max * 0.8 ? 0 : 1);
  list.sort((a, b) =>
    (tier(a) - tier(b)) ||
    (b.e.eligible - a.e.eligible) ||
    ((b.e.value ?? -1) - (a.e.value ?? -1)) ||
    (b.s - a.s));

  const catNames = [...q.cats].map((k) => CATEGORIES[k].label).join(", ");
  $("#summary").innerHTML = `${list.length} kampanya` +
    (q.amount ? ` · harcama: <b>${fmt(q.amount)} TL</b>` : " · <i>tutar yazarsan kazancı da hesaplarım</i>") +
    (catNames ? ` · ${catNames}` : "");

  if (!list.length) {
    res.innerHTML = `<div class="empty">Eşleşen kampanya bulunamadı. Daha genel bir ifade dene (örn. "market", "akaryakıt").</div>`;
    return;
  }
  res.innerHTML = list.slice(0, 60).map((r, i) => card(r, i === 0 && r.e.eligible && r.e.value > 0)).join("");
}

function esc(s) { return (s || "").replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch])); }

function card({ c, e }, best) {
  const dl = daysLeft(c.end);
  let valueHtml;
  if (e.value != null) {
    valueHtml = e.value > 0
      ? `<div class="value"><b>≈${fmt(e.value)} TL</b><small>${esc(e.sub)}</small></div>`
      : `<div class="value neutral"><b>${c.min_spend ? fmt(c.min_spend) + " TL" : "—"}</b><small>${c.min_spend ? "min. harcama" : "hesaplanamadı"}</small></div>`;
  } else {
    valueHtml = `<div class="value ${e.label === "Fırsat" ? "neutral" : ""}"><b>${esc(e.label)}</b><small>${esc(e.sub)}</small></div>`;
  }
  const badges = [
    `<span class="badge ${c.program}">${({ Axess: "Akbank Axess", Akbank: "Akbank Mobil" })[c.program] || c.program}</span>`,
    ...c.categories.slice(0, 2).map((x) => `<span class="badge">${esc(x)}</span>`),
    dl != null && dl <= 7 && dl >= 0 ? `<span class="badge soon">Son ${dl} gün</span>` : "",
    c.end && dl > 7 && dl < 3650 ? `<span class="badge">${new Date(c.end).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })} bitiyor</span>` : "",
  ].join("");
  const rows = [];
  if (c.min_spend) rows.push(`<div class="row"><span class="k">Min. harcama:</span> ${fmt(c.min_spend)} TL</div>`);
  if (c.reward?.per_spend) rows.push(`<div class="row"><span class="k">Kural:</span> her ${fmt(c.reward.per_spend)} TL'ye ${fmt(c.reward.per_reward)} TL${c.reward.cap ? `, toplam ${fmt(c.reward.cap)} TL'ye kadar` : ""}</div>`);
  if (c.join) rows.push(`<div class="row"><span class="k">Katılım:</span> ${esc(c.join)}</div>`);
  if (c.code) rows.push(`<div class="row"><span class="k">Kod:</span> <code class="copy" data-copy="${esc(c.code)}">${esc(c.code)}</code></div>`);
  return `<article class="card ${best ? "best" : ""}">
    ${valueHtml}
    <div>
      <p class="title"><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a></p>
      <div class="meta">${badges}</div>
      ${rows.join("")}
      ${c.note ? `<div class="warn">${esc(c.note)}</div>` : ""}
      <details><summary>Kampanya metni</summary><pre>${esc(c.text)}</pre></details>
    </div>
  </article>`;
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 1600);
}

async function load() {
  const r = await fetch("data/campaigns.json", { cache: "no-cache" });
  const j = await r.json();
  // Başlık + metnin ilk satırları (akbank.com başlıkları kısa, açıklama ilk satırda) güçlü eşleşme alanı
  DATA = j.campaigns.map((c) => ({ ...c, _title: norm(c.title + " " + (c.text || "").slice(0, 160)), _text: norm(c.text) }));
  $("#updated").textContent = `${DATA.length} aktif kampanya · son güncelleme ${new Date(j.updated).toLocaleString("tr-TR")}`;
  render();
}

$("#chips").innerHTML = Object.entries(CATEGORIES).map(([k, c]) => `<button class="chip" data-q="${k}">${c.label}</button>`).join("");
$("#chips").addEventListener("click", (e) => {
  const b = e.target.closest(".chip"); if (!b) return;
  const amt = parseQuery($("#q").value).amount;
  $("#q").value = `${CATEGORIES[b.dataset.q].kw[0]}${amt ? " " + amt + " TL" : ""}`;
  render();
});
$("#search").addEventListener("submit", (e) => { e.preventDefault(); render(); });
$("#q").addEventListener("input", () => { clearTimeout(window._t); window._t = setTimeout(render, 250); });
document.querySelectorAll(".filters input").forEach((i) => i.addEventListener("change", render));
document.addEventListener("click", (e) => {
  const c = e.target.closest("[data-copy]");
  if (c) { navigator.clipboard?.writeText(c.dataset.copy); toast(`${c.dataset.copy} kopyalandı`); }
});
$("#refresh").addEventListener("click", async () => {
  await fetch("api/refresh", { method: "POST" });
  toast("Kampanyalar güncelleniyor (~1-2 dk)...");
  const poll = setInterval(async () => {
    const s = await (await fetch("api/status")).json();
    if (!s.running) { clearInterval(poll); await load(); toast(s.last_error ? "Güncelleme hatası" : "Güncellendi"); }
  }, 3000);
});

// "Güncelle" düğmesi sadece yerel sunucuda (server.py) çalışır; GitHub Pages'te gizle
fetch("api/status").then((r) => { if (!r.ok) throw 0; return r.json(); })
  .then(() => { $("#refresh").hidden = false; }).catch(() => {});
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

load();
