import sys
import json
from urllib.parse import quote_plus

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def products_of(txt):
    try:
        obj = json.loads(txt)
    except Exception:
        return None
    return obj.get("products") or (obj.get("data") or {}).get("products") or []


def main():
    query = " ".join(sys.argv[1:]) or "футболка женская"
    print(f"Запрос: {query!r}\n")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright не установлен. Сначала выполни:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return

    api = ("https://www.wildberries.ru/__internal/u-search/exactmatch/sng/common/v18/search"
           "?ab_testid=catboost_exp_2&appType=1&curr=kzt&dest=85&hide_dflags=131072"
           "&hide_dtype=11;13;15&hide_vflags=4294967296&inheritFilters=false&lang=ru"
           f"&locale=kz&page=1&query={quote_plus(query)}&resultset=catalog&sort=popular"
           "&spp=30&suppressSpellcheck=false")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(locale="ru-RU", user_agent=UA)
        page = ctx.new_page()

        print("ШАГ 1. Открываю главную wildberries.ru (смотри в окно браузера) ...")
        page.goto("https://www.wildberries.ru/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        print("   заголовок страницы:", repr(page.title()))

        print("\nШАГ 2. Пробую fetch к API из контекста браузера ...")
        for i in range(4):
            res = page.evaluate(
                "async (u) => { try { const r = await fetch(u, {headers:{'Accept':'*/*'}}); "
                "const t = await r.text(); return {status:r.status, text:t}; } "
                "catch(e) { return {status:0, text:String(e)}; } }", api)
            txt = res.get("text", "") or ""
            print(f"   попытка {i+1}: HTTP {res.get('status')}, длина ответа {len(txt)}")
            prods = products_of(txt)
            if prods:
                print("   >>> ТОВАРОВ:", len(prods))
                print("   >>> первый:", prods[0].get("name"))
                open("wb_browser_ok.txt", "w", encoding="utf-8").write(txt[:4000])
                print("   >>> начало ответа сохранено в wb_browser_ok.txt")
                browser.close()
                print("\nУСПЕХ. Браузерная стратегия рабочая — ставь WB_STRATEGY='browser'.")
                return
            if "antibot" in txt or "challenge" in txt.lower():
                print("   antibot ещё держит, жду и пробую снова ...")
            page.wait_for_timeout(5000)

        print("\nШАГ 3. Пробую перейти прямо на API-адрес ...")
        page.goto(api, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        print("   длина body:", len(body))
        open("wb_browser_goto.txt", "w", encoding="utf-8").write(body[:4000])
        prods = products_of(body)
        if prods:
            print("   >>> ТОВАРОВ:", len(prods), "- УСПЕХ, ставь WB_STRATEGY='browser'.")
        else:
            print("   товаров не видно. Сохранил начало в wb_browser_goto.txt.")
            print("   Если там antibot/challenge - значит даже видимый браузер не проходит,")
            print("   и тогда WB-Казахстан из кода недоступен (используй WB_STRATEGY='ru').")

        browser.close()


if __name__ == "__main__":
    main()
