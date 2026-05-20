from flask import Flask, render_template, request, jsonify
import calendar
import os
import sys
from datetime import datetime

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from budget import (
    set_monthly_budget,
    get_monthly_budget,
    set_category_limit,
    get_category_limits,
    get_remaining_budget,
)
from approver import judge_expense, judge_batch_expense, detect_category
from ledger import add_record, get_all_records, get_month_spent, get_category_spent
from bills import generate_daily_bill, generate_weekly_bill, export_bill, get_meal_suggestion, check_monthly_reset
from storage import load_data, save_data

app = Flask(__name__)

# 启动时检查是否需要月度重置
check_monthly_reset()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def api_get_config():
    config = load_data().get("api_config", {})
    # Don't return the actual api_key to frontend for security
    return jsonify({
        "enabled": config.get("enabled", False),
        "base_url": config.get("base_url", "https://api.deepseek.com"),
        "model": config.get("model", "deepseek-v4-pro"),
        "has_key": bool(config.get("api_key", "")),
        "dietary_preferences": config.get("dietary_preferences", ""),
    })


@app.route("/api/config", methods=["POST"])
def api_set_config():
    data = request.get_json()
    store = load_data()
    config = store.get("api_config", {})

    if "enabled" in data:
        config["enabled"] = bool(data["enabled"])
    if "api_key" in data:
        config["api_key"] = data["api_key"]
    if "base_url" in data:
        config["base_url"] = data["base_url"]
    if "model" in data:
        config["model"] = data["model"]
    if "dietary_preferences" in data:
        config["dietary_preferences"] = data["dietary_preferences"]

    store["api_config"] = config
    save_data(store)
    return jsonify({"success": True})


@app.route("/api/budget", methods=["GET"])
def api_get_budget():
    import calendar
    limits = get_category_limits()
    categories = []
    total_limit = sum(l for l in limits.values() if l > 0)

    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    remaining_days = last_day - now.day + 1
    if remaining_days < 1:
        remaining_days = 1
    daily_budget = get_remaining_budget() / remaining_days

    for cat, limit in limits.items():
        spent = get_category_spent(cat)
        pct = (spent / limit * 100) if limit > 0 else 0
        # 今日建议分配
        alloc = 0
        if total_limit > 0 and limit > 0:
            alloc = daily_budget * (limit / total_limit)
            cat_rem = limit - spent
            if alloc > cat_rem:
                alloc = cat_rem
        categories.append({
            "name": cat,
            "limit": limit,
            "spent": spent,
            "percent": round(pct, 1),
            "daily_alloc": round(alloc, 2) if alloc > 0 else 0,
        })
    return jsonify({
        "monthly_budget": get_monthly_budget(),
        "month_spent": get_month_spent(),
        "remaining": get_remaining_budget(),
        "daily_budget": round(daily_budget, 2),
        "remaining_days": remaining_days,
        "categories": categories,
    })


@app.route("/api/budget", methods=["POST"])
def api_set_budget():
    data = request.get_json()
    amount = float(data.get("amount", 0))
    set_monthly_budget(amount)
    return jsonify({"success": True, "monthly_budget": amount})


@app.route("/api/limits", methods=["POST"])
def api_set_limit():
    data = request.get_json()
    category = data.get("category", "")
    amount = float(data.get("amount", 0))
    set_category_limit(category, amount)
    return jsonify({"success": True, "category": category, "limit": amount})


@app.route("/api/approve", methods=["POST"])
def api_approve():
    data = request.get_json()
    amount = float(data.get("amount", 0))
    description = data.get("description", "")
    result = judge_expense(amount, description)
    cat = result["category"]
    add_record(amount, description, cat, approved=result["approved"], reason=result.get("reason", ""))
    return jsonify(result)


@app.route("/api/approve/batch", methods=["POST"])
def api_approve_batch():
    data = request.get_json()
    items = data.get("items", [])
    result = judge_batch_expense(items)
    reason = result.get("reason", "")
    for item in result.get("items", []):
        add_record(
            item["amount"],
            item["description"],
            item["category"],
            approved=result["approved"],
            reason=reason,
        )
    return jsonify(result)


@app.route("/api/records", methods=["GET"])
def api_records():
    records = get_all_records()
    return jsonify({"records": list(reversed(records))})


@app.route("/api/records", methods=["DELETE"])
def api_clear_records():
    store = load_data()
    store["records"] = []
    save_data(store)
    return jsonify({"success": True})


@app.route("/api/bill/daily", methods=["GET"])
def api_daily_bill():
    bill = generate_daily_bill()
    return jsonify({"bill": bill})


@app.route("/api/bill/weekly", methods=["GET"])
def api_weekly_bill():
    bill = generate_weekly_bill()
    return jsonify({"bill": bill})


@app.route("/api/meal-suggestion", methods=["GET"])
def api_meal_suggestion():
    return jsonify(get_meal_suggestion())


if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
    else:
        app.run(debug=True, host='0.0.0.0', port=5000)
