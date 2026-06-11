from __future__ import annotations

import re
import time
import threading
from urllib.parse import quote_plus

import requests


KASPI_CITY = "710000000"

WB_DEST = "85"
WB_STRATEGY = "browser"
WB_HEADLESS = True

MAX_ITEMS = 48
PAGE_SIZE = 12

REQUEST_DELAY = 0.8
PAGE_DELAY = 0.4
HTTP_TIMEOUT = 20
CACHE_TTL = 300

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def get_json(session, url, params=None, headers=None):
    try:
        r = session.get(url, params=params, headers=headers or {}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def item(name, *, price=None, rating=None, reviews=0, url="", image=None, currency=None):
    return {"name": (name or "").strip(), "price": to_int(price),
            "rating": to_float(rating), "reviews": int(reviews or 0),
            "url": url or "", "image": image, "currency": currency}


def to_int(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def to_float(value):
    try:
        return float(value) if value not in (None, "", 0) else None
    except (TypeError, ValueError):
        return None


def wb_image(nm_id):
    try:
        nm = int(nm_id)
    except (TypeError, ValueError):
        return None
    vol, part = nm // 100000, nm // 1000
    ranges = [(143,"01"),(287,"02"),(431,"03"),(719,"04"),(1007,"05"),(1061,"06"),
              (1115,"07"),(1169,"08"),(1313,"09"),(1601,"10"),(1655,"11"),(1919,"12"),
              (2045,"13"),(2189,"14"),(2405,"15"),(2621,"16"),(2837,"17"),(3053,"18"),
              (3269,"19"),(3485,"20"),(3709,"21"),(3933,"22"),(4157,"23"),(4381,"24"),
              (4605,"25"),(4877,"26"),(5163,"27"),(5448,"28"),(5651,"29"),(5826,"30")]
    basket = "31"
    for limit_vol, b in ranges:
        if vol <= limit_vol:
            basket = b
            break
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm}/images/c246x328/1.webp"


REGISTRY: list[dict] = []


def marketplace(name, currency="₸", color="#6c5ce7"):
    def deco(fn):
        REGISTRY.append({"name": name, "currency": currency, "color": color, "fn": fn})
        return fn
    return deco


@marketplace("Kaspi", currency="₸", color="#f14635")
def kaspi(query, limit, session):
    out = []
    for page in range(0, 6):
        data = get_json(
            session,
            "https://kaspi.kz/yml/product-view/pl/results",
            params={"text": query, "page": str(page), "all": "false",
                    "fl": "true", "ui": "d", "i": "-1", "c": KASPI_CITY},
            headers={"Accept": "application/json, text/*",
                     "Referer": f"https://kaspi.kz/shop/search/?text={quote_plus(query)}",
                     "X-KS-City": KASPI_CITY, "X-Requested-With": "XMLHttpRequest"},
        )
        cards = data if isinstance(data, list) else (data or {}).get("data") or []
        if isinstance(cards, dict):
            cards = cards.get("cards") or []
        if not cards:
            break
        for c in cards:
            if not isinstance(c, dict):
                continue
            href = c.get("shopLink") or c.get("link") or ""
            if href.startswith("/"):
                href = f"https://kaspi.kz{href}"
            previews = c.get("previewImages") or []
            img = previews[0].get("small") if previews and isinstance(previews[0], dict) else None
            out.append(item(c.get("title"), price=c.get("unitPrice") or c.get("price"),
                            rating=c.get("rating"), reviews=c.get("reviewsQuantity"),
                            url=href, image=img))
        if len(out) >= limit:
            break
        time.sleep(PAGE_DELAY)
    return out[:limit]


def _wb_request(session, url, params, headers, retries, wait):
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        except Exception:
            return None
        if r.status_code == 429:
            time.sleep(wait)
            continue
        try:
            return r.json()
        except Exception:
            return None
    return None


def _wb_products(data):
    return (data or {}).get("products") or ((data or {}).get("data") or {}).get("products") or []


def _wb_ru(session, query):
    headers = {"Accept": "*/*", "Referer": "https://www.wildberries.ru/"}
    params = {"appType": "1", "curr": "rub", "dest": "-1257786", "lang": "ru",
              "page": "1", "query": query, "resultset": "catalog",
              "sort": "popular", "spp": "30", "suppressSpellcheck": "false"}
    for url in ("https://search.wb.ru/exactmatch/ru/common/v18/search",
                "https://u-search.wb.ru/exactmatch/ru/common/v18/search"):
        data = _wb_request(session, url, params, headers, retries=3, wait=3)
        prods = _wb_products(data)
        if prods:
            return prods, "₽"
    return [], "₽"


def _wb_kz(session, query, patient=False):
    hosts = ("https://search.wb.ru/exactmatch/sng/common/v18/search",
             "https://u-search.wb.ru/exactmatch/sng/common/v18/search")
    base = {"appType": "1", "dest": WB_DEST, "hide_dtype": "13;15",
            "lang": "ru", "locale": "kz", "page": "1", "query": query,
            "resultset": "catalog", "sort": "popular", "spp": "30",
            "suppressSpellcheck": "false"}
    headers = {"Accept": "*/*", "Origin": "https://www.wildberries.ru",
               "Referer": "https://www.wildberries.ru/"}
    retries, wait, gap = (6, 6, 2.0) if patient else (3, 3, 0.5)
    for curr, sym in (("kzt", "₸"), ("rub", "₽")):
        for url in hosts:
            data = _wb_request(session, url, {**base, "curr": curr}, headers, retries, wait)
            prods = _wb_products(data)
            if prods:
                return prods, sym
            time.sleep(gap)
    return [], "₸"


def _wb_browser(query):
    import json as _json
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], "₸"
    url = ("https://www.wildberries.ru/__internal/u-search/exactmatch/sng/common/v18/search"
           "?ab_testid=catboost_exp_2&appType=1&curr=kzt"
           f"&dest={WB_DEST}&hide_dflags=131072&hide_dtype=11;13;15"
           "&hide_vflags=4294967296&inheritFilters=false&lang=ru&locale=kz&page=1"
           f"&query={quote_plus(query)}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false")
    data = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=WB_HEADLESS,
                args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(locale="ru-RU", user_agent=USER_AGENT)
            page = ctx.new_page()
            page.goto("https://www.wildberries.ru/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)
            for _ in range(3):
                try:
                    data = page.evaluate(
                        "async (u) => { try { const r = await fetch(u, {headers:{'Accept':'*/*'}}); "
                        "return await r.json(); } catch(e) { return null; } }", url)
                except Exception:
                    data = None
                if _wb_products(data):
                    break
                page.wait_for_timeout(4000)
            if not _wb_products(data):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(6000)
                    data = _json.loads(page.evaluate("() => document.body ? document.body.innerText : ''"))
                except Exception:
                    pass
            browser.close()
    except Exception:
        return [], "₸"
    return _wb_products(data), "₸"


def _wb_to_items(products, currency, limit):
    out = []
    for it in products[:limit]:
        if not isinstance(it, dict):
            continue
        price = None
        sizes = it.get("sizes") or []
        if sizes and isinstance(sizes[0], dict):
            po = sizes[0].get("price") or {}
            raw = po.get("product") or po.get("total") or po.get("basic")
            price = int(raw) // 100 if raw else None
        if price is None and it.get("salePriceU"):
            price = int(it["salePriceU"]) // 100
        brand = (it.get("brand") or "").strip()
        name = (it.get("name") or "").strip()
        out.append(item(f"{brand} {name}".strip() if brand else name, price=price,
                        rating=it.get("reviewRating") or it.get("nmReviewRating"),
                        reviews=it.get("feedbacks"),
                        url=f"https://www.wildberries.ru/catalog/{it.get('id')}/detail.aspx",
                        image=wb_image(it.get("id")), currency=currency))
    return out


@marketplace("Wildberries", currency="₸", color="#cb11ab")
def wildberries(query, limit, session):
    if WB_STRATEGY == "ru":
        products, currency = _wb_ru(session, query)
    elif WB_STRATEGY == "browser":
        products, currency = _wb_browser(query)
    elif WB_STRATEGY == "hybrid":
        products, currency = _wb_kz(session, query)
        if not products:
            products, currency = _wb_ru(session, query)
    else:  # "kz" / "kz_patient"
        products, currency = _wb_kz(session, query, patient=(WB_STRATEGY == "kz_patient"))
    return _wb_to_items(products, currency, limit)


_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def _format(raw, name, currency):
    res = []
    for it in raw:
        price = it.get("price")
        d = dict(it)
        d["marketplace"] = name
        d["currency"] = it.get("currency") or currency
        d["price_text"] = f"{price:,}".replace(",", " ") if price else None
        res.append(d)
    return res


def _fetch_all(query):
    key = query.lower()
    now = time.time()
    with _lock:
        if key in _cache and now - _cache[key][0] < CACHE_TTL:
            return _cache[key][1]

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT,
                            "Accept-Language": "ru-RU,ru;q=0.9,kk;q=0.8"})

    results, colors = {}, {}
    for mp in REGISTRY:
        try:
            raw = mp["fn"](query, MAX_ITEMS, session)
        except Exception:
            raw = []
        formatted = _format(raw, mp["name"], mp["currency"])
        results[mp["name"]] = formatted
        colors[mp["name"]] = mp["color"]
        time.sleep(REQUEST_DELAY)

    full = {"results": results, "colors": colors}
    with _lock:
        _cache[key] = (now, full)
    return full


def search_all(query, page=1):
    query = (query or "").strip()
    if not query:
        return {"query": "", "results": {}, "colors": {},
                "page": 1, "total_pages": 1, "totals": {}, "cached": False}

    with _lock:
        cached = query.lower() in _cache and time.time() - _cache[query.lower()][0] < CACHE_TTL
    full = _fetch_all(query)

    page = max(1, int(page or 1))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    results_page, totals, max_count = {}, {}, 0
    for mp, items in full["results"].items():
        totals[mp] = len(items)
        max_count = max(max_count, len(items))
        results_page[mp] = items[start:end]

    return {
        "query": query,
        "results": results_page,
        "colors": full["colors"],
        "page": page,
        "total_pages": max(1, -(-max_count // PAGE_SIZE)),
        "totals": totals,
        "page_size": PAGE_SIZE,
        "cached": cached,
    }


if __name__ == "__main__":
    import sys
    data = search_all(" ".join(sys.argv[1:]) or "холодильник", page=1)
    print(f"Страница {data['page']} из {data['total_pages']} | всего: {data['totals']}")
    for mp, items in data["results"].items():
        print(f"\n=== {mp} ===")
        for it in items:
            price = f"{it['price_text']} {it['currency']}" if it["price_text"] else "—"
            print(f"  {it['name'][:55]:55} | {price:>14} | r={it['rating']} | отз={it['reviews']}")