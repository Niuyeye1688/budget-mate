import calendar
import json
import urllib.request
from datetime import datetime
from ledger import get_today_records, get_week_records, get_month_spent
from budget import get_monthly_budget, get_category_limits, get_remaining_budget
import os
from storage import load_data, save_data, DATA_FILE


def format_records(records):
    approved = [r for r in records if r.get("approved", True)]
    if not approved:
        return "  暂无记录"
    lines = []
    total = 0
    for r in approved:
        lines.append(f"  [{r['date']}] {r['amount']:.2f} 元 | {r['category']} | {r['description']}")
        total += r["amount"]
    lines.append(f"\n  合计支出: {total:.2f} 元")
    return "\n".join(lines)


def generate_daily_bill():
    today = datetime.now().strftime("%Y-%m-%d")
    records = get_today_records()
    lines = [
        "=" * 50,
        f"[每日账单] {today}",
        "=" * 50,
        format_records(records),
        "=" * 50,
        f"[本月预算] {get_monthly_budget():.2f} 元",
        f"[本月已用] {get_month_spent():.2f} 元",
        f"[本月剩余] {get_remaining_budget():.2f} 元",
        "=" * 50,
    ]
    return "\n".join(lines)


def generate_weekly_bill():
    now = datetime.now()
    weekday = now.weekday()
    start = now.replace(day=now.day - weekday).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    records = get_week_records()

    category_stats = {}
    total = 0
    for r in records:
        if r["approved"]:
            category_stats[r["category"]] = category_stats.get(r["category"], 0) + r["amount"]
            total += r["amount"]

    cat_lines = []
    limits = get_category_limits()
    for cat, spent in category_stats.items():
        limit = limits.get(cat, 0)
        if limit > 0:
            pct = (spent / limit) * 100
            cat_lines.append(f"  {cat}: {spent:.2f} 元 / {limit:.2f} 元 ({pct:.1f}%)")
        else:
            cat_lines.append(f"  {cat}: {spent:.2f} 元 (无上限)")

    lines = [
        "=" * 50,
        f"[每周账单] {start} 至 {end}",
        "=" * 50,
        "【明细】",
        format_records(records),
        "",
        "【分类统计】",
    ]
    if cat_lines:
        lines.extend(cat_lines)
    else:
        lines.append("  本周无支出")
    lines.extend([
        "",
        f"【汇总】",
        f"  本周总支出: {total:.2f} 元",
        f"  本月预算: {get_monthly_budget():.2f} 元",
        f"  本月剩余: {get_remaining_budget():.2f} 元",
        "=" * 50,
    ])
    return "\n".join(lines)


def export_bill(content, filename=None):
    if filename is None:
        filename = f"bill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def _get_meal_by_hour(hour):
    """根据小时判断餐段，返回 (餐段名, 剩余餐段列表)。只分午餐和晚餐。"""
    meals = [
        ("午餐", list(range(11, 17))),           # 11:00-16:59
        ("晚餐", list(range(17, 24)) + list(range(0, 11))),  # 17:00-10:59
    ]
    remaining = []
    found = False
    for name, hours in meals:
        if hour in hours:
            found = True
            remaining.append(name)
        elif found:
            remaining.append(name)
    if found:
        return remaining[0], remaining
    return None, []


def get_meal_suggestion():
    """根据当前时间和剩余预算，返回用餐建议"""
    now = datetime.now()
    hour = now.hour

    meal, remaining_meals = _get_meal_by_hour(hour)
    if meal is None:
        return {"meal": None}

    # 计算当月剩余天数（含今天）
    last_day = calendar.monthrange(now.year, now.month)[1]
    remaining_days = last_day - now.day + 1
    if remaining_days < 1:
        remaining_days = 1

    # 日均预算
    monthly_remaining = get_remaining_budget()
    daily_budget = monthly_remaining / remaining_days

    # 今天餐饮已用
    today_records = get_today_records()
    daily_spent = sum(
        r["amount"]
        for r in today_records
        if r["category"] == "餐饮" and r["approved"]
    )

    # 今天剩余餐饮预算
    daily_left = daily_budget - daily_spent
    if daily_left < 0:
        daily_left = 0

    # 建议金额 = 今天剩余 ÷ 今天剩余餐数
    remaining_count = len(remaining_meals)
    suggestion = daily_left / remaining_count if remaining_count > 0 else 0

    # AI 推荐
    recommendations = []
    data = load_data()
    config = data.get("api_config", {})
    if config.get("enabled") and config.get("api_key"):
        try:
            preferences = config.get("dietary_preferences", "")
            recommendations = ai_recommend_meal(meal, suggestion, preferences)
        except Exception:
            pass

    return {
        "meal": meal,
        "suggestion": round(suggestion, 2),
        "daily_budget": round(daily_budget, 2),
        "daily_spent": round(daily_spent, 2),
        "remaining_days": remaining_days,
        "recommendations": recommendations,
    }


def ai_recommend_meal(meal, budget, preferences=""):
    """调用 AI 获取用餐推荐"""
    data = load_data()
    config = data.get("api_config", {})
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "https://api.deepseek.com")
    model = config.get("model", "deepseek-chat")

    pref_text = f"\n用户饮食偏好/忌口：{preferences}" if preferences else ""

    prompt = f"""你是贴心的饮食顾问，帮用户推荐今天{meal}吃什么。

用户预算：建议控制在 {budget:.0f} 元内。{pref_text}

要求：
1. 推荐 2-3 个符合预算的食物选项
2. 每个选项包含：名称、预估价格（整数）、一句话推荐理由
3. 推荐要接地气、实用，避开用户忌口的食物
4. 如果预算很低（<15元），优先推荐省钱又饱腹的选择
5. 如果预算充裕（>40元），可以推荐稍微丰富一点的

输出严格JSON数组，不要有任何其他文字：
[{{"name": "选项名称", "price": 预估价格, "reason": "推荐理由"}}]"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个贴心的饮食顾问，帮助用户选择今天吃什么。输出必须是JSON格式。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
    }

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed = json.loads(content)
        recommendations = []
        for item in parsed:
            recommendations.append({
                "name": item.get("name", ""),
                "price": int(item.get("price", 0)),
                "reason": item.get("reason", ""),
            })
        return recommendations


def generate_monthly_bill(month):
    """生成指定月份的账单"""
    data = load_data()
    records = data.get("records", [])
    month_records = [r for r in records if r["date"].startswith(month)]

    category_stats = {}
    total = 0
    approved_total = 0
    for r in month_records:
        if r["approved"]:
            category_stats[r["category"]] = category_stats.get(r["category"], 0) + r["amount"]
            total += r["amount"]
            approved_total += r["amount"]

    cat_lines = []
    limits = get_category_limits()
    for cat, spent in category_stats.items():
        limit = limits.get(cat, 0)
        if limit > 0:
            pct = (spent / limit) * 100
            cat_lines.append(f"  {cat}: {spent:.2f} 元 / {limit:.2f} 元 ({pct:.1f}%)")
        else:
            cat_lines.append(f"  {cat}: {spent:.2f} 元 (无上限)")

    remaining = get_monthly_budget() - total

    lines = [
        "=" * 50,
        f"[月度账单] {month}",
        "=" * 50,
        "【明细】",
        format_records(month_records),
        "",
        "【分类统计】",
    ]
    if cat_lines:
        lines.extend(cat_lines)
    else:
        lines.append("  本月无支出")
    lines.extend([
        "",
        f"【汇总】",
        f"  本月总支出: {total:.2f} 元",
        f"  本月预算: {get_monthly_budget():.2f} 元",
        f"  本月剩余: {remaining:.2f} 元",
        "=" * 50,
    ])
    return "\n".join(lines)


def check_monthly_reset():
    """检查是否需要月度重置，如果是则生成上月账单并清空记录"""
    data = load_data()
    current_month = datetime.now().strftime("%Y-%m")
    stored_month = data.get("current_month", "")

    if stored_month and stored_month != current_month:
        # 新月到了，生成上月账单
        bill = generate_monthly_bill(stored_month)
        bill_dir = os.path.join(os.path.dirname(DATA_FILE), "bills")
        os.makedirs(bill_dir, exist_ok=True)
        filename = os.path.join(bill_dir, f"bill_month_{stored_month}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(bill)

        # 清空记录，更新当前月份
        data["records"] = []
        data["current_month"] = current_month
        save_data(data)
        print(f"[月度重置] 已生成 {stored_month} 月度账单: {filename}")
    elif not stored_month:
        # 首次使用，设置当前月份
        data["current_month"] = current_month
        save_data(data)
