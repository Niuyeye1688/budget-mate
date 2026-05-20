from datetime import datetime, timedelta
from storage import load_data, save_data, get_current_month


def add_record(amount, description, category, approved, reason=""):
    data = load_data()
    record = {
        "id": len(data["records"]) + 1,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "description": description,
        "category": category,
        "approved": approved,
        "reason": reason,
    }
    data["records"].append(record)
    save_data(data)
    return record


def get_all_records():
    return load_data().get("records", [])


def get_month_spent():
    month = get_current_month()
    records = load_data().get("records", [])
    return sum(r["amount"] for r in records if r["date"].startswith(month) and r["approved"])


def get_category_spent(category):
    month = get_current_month()
    records = load_data().get("records", [])
    return sum(
        r["amount"]
        for r in records
        if r["date"].startswith(month) and r["category"] == category and r["approved"]
    )


def get_category_spent_recent(category, hours=1):
    """获取最近 N 小时内某分类的已批准支出总额"""
    now = datetime.now()
    cutoff = now - timedelta(hours=hours)
    records = load_data().get("records", [])
    total = 0
    for r in records:
        if not r["approved"] or r["category"] != category:
            continue
        try:
            rd = datetime.strptime(r["date"], "%Y-%m-%d %H:%M:%S")
            if rd >= cutoff:
                total += r["amount"]
        except ValueError:
            continue
    return total


def get_recent_records(category, minutes=30):
    """获取最近 N 分钟内某分类的已批准支出明细"""
    now = datetime.now()
    cutoff = now - timedelta(minutes=minutes)
    records = load_data().get("records", [])
    result = []
    for r in records:
        if not r["approved"] or r["category"] != category:
            continue
        try:
            rd = datetime.strptime(r["date"], "%Y-%m-%d %H:%M:%S")
            if rd >= cutoff:
                result.append({
                    "amount": r["amount"],
                    "description": r["description"],
                    "date": r["date"],
                })
        except ValueError:
            continue
    return result


def get_today_records():
    today = datetime.now().strftime("%Y-%m-%d")
    records = load_data().get("records", [])
    return [r for r in records if r["date"].startswith(today)]


def get_week_records():
    now = datetime.now()
    weekday = now.weekday()
    start_of_week = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_week.replace(day=now.day - weekday)
    records = load_data().get("records", [])
    result = []
    for r in records:
        rd = datetime.strptime(r["date"], "%Y-%m-%d %H:%M:%S")
        if rd >= start_of_week:
            result.append(r)
    return result
