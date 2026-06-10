from flask import Flask, render_template, request, jsonify

from parsers import search_all

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Пустой запрос"}), 400
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        return jsonify(search_all(query, page=page))
    except Exception as e:
        return jsonify({"error": f"Ошибка поиска: {e}"}), 500


@app.errorhandler(404)
def _404(e):
    return jsonify({"error": "Не найдено"}), 404


@app.errorhandler(500)
def _500(e):
    return jsonify({"error": "Внутренняя ошибка сервера"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)