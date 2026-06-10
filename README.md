# Поиск по маркетплейсам

Веб-приложение для поиска и сравнения товаров на Kaspi и Wildberries.
Бэкенд на Flask, фронтенд — одна HTML-страница.

## Структура

```
mp/
├── app.py
├── parsers.py
├── requirements.txt
└── templates/
    └── index.html
```

## Запуск

```
pip install -r requirements.txt
python app.py
```

Открыть в браузере: http://127.0.0.1:5000

Запуск парсера без интерфейса:

```
python parsers.py холодильник
```

## Настройки (вверху parsers.py)

- `KASPI_CITY` — код города Kaspi (710000000 — Астана, 750000000 — Алматы)
- `WB_DEST`, `WB_CURRENCY` — регион и валюта выдачи Wildberries
- `MAX_ITEMS` — сколько товаров набирать с каждого сайта
- `PAGE_SIZE` — количество товаров на странице