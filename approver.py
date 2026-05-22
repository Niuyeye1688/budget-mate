import calendar
import json
import urllib.request
from datetime import datetime
from storage import load_data, get_current_month
from ledger import get_month_spent, get_category_spent, get_category_spent_recent, get_recent_records

# 统一 system message，所有 AI 调用共享，最大化 DeepSeek 前缀缓存命中率
SYSTEM_MESSAGE = """你是一位有鲜明个性的私人财务顾问，对合理支出温柔鼓励，对浪费行为犀利吐槽。输出必须是JSON格式。

语气要求：
- 如果批准：语气温柔亲切，像贴心闺蜜/兄弟一样，给用户满满的鼓励和认可
- 如果拒绝：语气犀利毒舌，直接指出问题，带一点"恨铁不成钢"的感觉

判断标准：
1. 核心目标：让预算撑到月底不为零。日均可用预算是最重要的参考红线
2. 餐饮类：正常一餐不应明显超过日均预算，超出需有正当理由（如聚餐、请客）。如果最近1小时内有其他餐饮消费，合并视为"本次一餐"判断
3. 交通类：日常通勤单次不应超过日均预算的2倍，打车非急事应拒绝。如果最近1小时内有其他交通消费，合并视为"本次出行"判断
4. 购物类：非必需品优先拒绝，奢侈品直接拒绝
5. 娱乐类：每月不超过 2-3 次，单次不超过日均预算的3倍
6. 明显浪费、冲动消费、可替代方案更便宜的 → 拒绝

消费分类规则：根据描述判断属于餐饮/交通/购物/娱乐/其他，只输出分类名。

饮食推荐规则：推荐2-3个符合预算的食物选项，每个包含名称、预估价格、推荐理由。要接地气实用，避开用户忌口。如果预算很低（<15元），优先推荐省钱又饱腹的选择。如果预算充裕（>40元），可以推荐稍微丰富一点的。"""


def detect_category(description):
    desc = description.lower()
    keywords = {
        "餐饮": ["饭", "餐", "吃", "餐厅", "食堂", "外卖", "火锅", "烧烤", "咖啡", "奶茶", "菜", "请客", "聚餐", "酒", "食", "甜筒", "冰淇淋", "雪糕", "冰棍", "冰棒", "零食", "薯片", "饼干", "巧克力", "糖果", "面包", "蛋糕", "甜点", "甜品", "汉堡", "披萨", "炸鸡", "薯条", "小吃", "饮料", "可乐", "果汁", "矿泉水", "牛奶", "酸奶", "豆浆", "包子", "饺子", "面条", "米线", "河粉", "寿司", "沙拉", "粥", "油条", "煎饼", "烤肠"],
        "交通": ["车", "地铁", "公交", "出租", "滴滴", "打车", "加油", "油费", "停车", "高铁", "火车", "飞机", "票", "路费", "通勤"],
        "购物": ["买", "购物", "衣服", "鞋", "包", "化妆品", "超市", "便利店", "淘宝", "京东", "拼多多", "用品", "东西", "设备", "电器"],
        "娱乐": ["游戏", "电影", "唱", "玩", "旅游", "旅行", "门票", "会员", "视频", "音乐", "球", "健身", "娱乐", "休闲"],
    }
    for cat, words in keywords.items():
        for w in words:
            if w in desc:
                return cat
    return "其他"


def _check_rules(amount, category):
    """规则检查，返回 (approved, reasons, category)"""
    data = load_data()
    limits = data.get("category_limits", {})
    cat_limit = limits.get(category, 0)
    month_budget = data.get("monthly_budget", 0)
    month_spent = get_month_spent()
    cat_spent = get_category_spent(category)
    cat_spent_recent = get_category_spent_recent(category, hours=1)

    # 日消费限额
    today_records = get_today_records()
    today_approved = sum(r["amount"] for r in today_records if r.get("approved", True))
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    remaining_days = days_in_month - today.day + 1
    daily_budget = (month_budget - month_spent) / remaining_days if remaining_days > 0 else 0

    reasons = []
    approved = True

    if month_budget <= 0:
        reasons.append("本月总预算未设置或为 0")
        approved = False
    elif month_spent + amount > month_budget:
        reasons.append(f"本月已用 {month_spent:.2f} 元，加上这笔 {amount:.2f} 元将超出总预算 {month_budget:.2f} 元")
        approved = False

    # 日消费限额：今日已批 + 这笔不超过日均预算的 1.5 倍
    daily_limit = daily_budget * 1.5
    if daily_budget > 0 and today_approved + amount > daily_limit:
        reasons.append(f"今日已批 {today_approved:.2f} 元，加上这笔 {amount:.2f} 元将超出日限额 {daily_limit:.2f} 元（日均 {daily_budget:.2f} 元）")
        approved = False

    # 分类上限不能超过月度总预算
    effective_cat_limit = min(cat_limit, month_budget) if cat_limit > 0 else 0
    if effective_cat_limit > 0 and cat_spent + amount > effective_cat_limit:
        reasons.append(f"【{category}】分类本月已用 {cat_spent:.2f} 元，上限为 {effective_cat_limit:.2f} 元")
        approved = False

    if effective_cat_limit > 0 and cat_spent_recent + amount > effective_cat_limit:
        reasons.append(f"【{category}】最近1小时内已用 {cat_spent_recent:.2f} 元，加上这笔将超上限 {effective_cat_limit:.2f} 元")
        approved = False

    # 短时高频限制：1小时内同分类累计不超过月度总预算的 10%
    short_term_limit = month_budget * 0.05
    if cat_spent_recent + amount > short_term_limit:
        reasons.append(f"【{category}】最近1小时内已用 {cat_spent_recent:.2f} 元，加上这笔将超短时限额 {short_term_limit:.2f} 元")
        approved = False

    return approved, reasons, category


def ai_judge(amount, description, recent_items=None, recent_total=0, is_trip=False):
    data = load_data()
    config = data.get("api_config", {})
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "https://api.deepseek.com")
    model = config.get("model", "deepseek-chat")

    month_budget = data.get("monthly_budget", 0)
    month_spent = get_month_spent()
    remaining = month_budget - month_spent

    # 计算剩余天数和日均预算
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    remaining_days = days_in_month - today.day + 1
    daily_budget = remaining / remaining_days if remaining_days > 0 else 0
    current_date = today.strftime("%m月%d日")

    # 今日已批总额（含当前这笔之前的）
    today_records = get_today_records()
    today_approved = sum(r["amount"] for r in today_records if r.get("approved", True))
    today_remaining = daily_budget - today_approved

    cat_info = []
    for cat, limit in data.get("category_limits", {}).items():
        spent = get_category_spent(cat)
        recent = get_category_spent_recent(cat, hours=1)
        if limit > 0:
            cat_info.append(f"{cat}: 本月已用{spent:.0f}元/上限{limit:.0f}元，最近1小时已用{recent:.0f}元")
        else:
            cat_info.append(f"{cat}: 本月已用{spent:.0f}元/无上限，最近1小时已用{recent:.0f}元")

    cat_text = "；".join(cat_info) if cat_info else "暂无分类预算"

    # 行程审批上下文
    trip_context = ""
    if is_trip:
        trip_context = "\n【注意：这是行程审批，属于大额低频支出通道，使用次数很少，请适当放宽标准。在保证通过后这个月剩余的天数都还有足够的餐饮预算下可以通过。】\n"

    # 构建"本次外出"消费上下文
    recent_context = ""
    if recent_items:
        lines = "\n".join([f"- {item['description']} {item['amount']:.0f}元" for item in recent_items])
        total_with_current = recent_total + amount
        recent_context = f"""\n本次外出您在同分类已消费：
{lines}
加上这笔【{description}】{amount:.0f}元，本次外出合计 {total_with_current:.0f} 元。\n"""

    prompt = f"""用户当前财务状况：
- 月预算：{month_budget:.0f}元
- 本月已用：{month_spent:.0f}元
- 本月剩余：{remaining:.0f}元
- 今天是{current_date}，本月还剩 {remaining_days} 天
- 日均可用预算：{daily_budget:.0f}元
- 今日已批：{today_approved:.0f}元，今日剩余可用：{today_remaining:.0f}元
- 各分类使用情况：{cat_text}

用户申请支出：{amount:.0f}元
用途描述：{description}
{trip_context}{recent_context}
请根据用途描述判断属于哪个分类（餐饮/交通/购物/娱乐/其他）。
输出严格JSON，不要有任何其他文字：
{{"approved": true/false, "reason": "简短理由（不超过30字）", "category": "分类名"}}"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
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

        # Try to extract JSON from the response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed = json.loads(content)
        return {
            "approved": bool(parsed.get("approved", False)),
            "category": parsed.get("category", detect_category(description)),
            "reason": parsed.get("reason", "AI判断"),
        }


def ai_classify(description):
    data = load_data()
    config = data.get("api_config", {})
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "https://api.deepseek.com")
    model = config.get("model", "deepseek-chat")

    if not config.get("enabled") or not api_key:
        return None

    prompt = f"""消费描述：{description}"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
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

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"].strip()
            content = content.strip('"').strip("'").strip("【】").strip()
            valid_cats = ["餐饮", "交通", "购物", "娱乐", "其他"]
            if content in valid_cats:
                return content
            return None
    except Exception:
        return None


def judge_expense(amount, description):
    data = load_data()
    config = data.get("api_config", {})

    category = detect_category(description)

    # 获取最近30分钟同分类已批准消费（用于智能外出合并）
    recent_items = get_recent_records(category, minutes=30)
    recent_total = sum(item["amount"] for item in recent_items)

    trip_prefix = ""
    if recent_items:
        trip_total = recent_total + amount
        trip_prefix = f"本次外出【{category}】合计 {trip_total:.2f} 元（含之前已审批的 {recent_total:.2f} 元）。"

    # AI 模式下直接让 AI 全权判断
    if config.get("enabled") and config.get("api_key"):
        try:
            ai_result = ai_judge(amount, description, recent_items=recent_items, recent_total=recent_total)
            category = ai_result.get("category", category)
            reason = ai_result.get("reason", "AI判断通过")
            if trip_prefix:
                reason = trip_prefix + reason
            return {
                "approved": ai_result.get("approved", True),
                "category": category,
                "reason": reason,
            }
        except Exception:
            pass  # AI failed, fall through to rule-based

    # Rule-based fallback (AI disabled or failed)
    rule_approved, rule_reasons, category = _check_rules(amount, category)

    if amount > 1000 and rule_approved:
        rule_reasons.append(f"单笔 {amount:.2f} 元属于大额支出，请慎重考虑（已批准）")

    if rule_approved and not rule_reasons:
        rule_reasons.append(f"余额充足，分类【{category}】未超支，可以支出。")

    reason = "；".join(rule_reasons)
    if trip_prefix:
        reason = trip_prefix + reason

    return {
        "approved": rule_approved,
        "category": category,
        "reason": reason,
    }


def judge_batch_expense(items, is_trip=False):
    """
    批量审批。items = [{"amount": 15, "description": "午饭"}, ...]
    is_trip=True 时为行程审批，跳过日限额和短时高频限制。
    返回整体结果和每条子结果。
    """
    if not items:
        return {"approved": False, "reason": "没有提交任何支出项", "items": []}

    total_amount = sum(item.get("amount", 0) for item in items)
    descriptions = [item.get("description", "") for item in items]
    combined_desc = "；".join(f"{d} ({item['amount']:.0f}元)" for d, item in zip(descriptions, items))

    # 逐项检测分类
    item_results = []
    for item in items:
        cat = detect_category(item.get("description", ""))
        item_results.append({
            "amount": item["amount"],
            "description": item["description"],
            "category": cat,
        })

    # AI 模式下让关键词未识别的 item 单独分类
    ai_config = load_data().get("api_config", {})
    if ai_config.get("enabled") and ai_config.get("api_key"):
        for item in item_results:
            if item["category"] == "其他":
                ai_cat = ai_classify(item["description"])
                if ai_cat:
                    item["category"] = ai_cat

    # AI 模式下直接让 AI 全权判断
    config = load_data().get("api_config", {})
    if config.get("enabled") and config.get("api_key"):
        try:
            ai_result = ai_judge(total_amount, f"本次外出消费：{combined_desc}", is_trip=is_trip)
            return {
                "approved": ai_result.get("approved", True),
                "reason": ai_result.get("reason", "AI判断通过"),
                "total": total_amount,
                "items": item_results,
            }
        except Exception:
            pass  # AI failed, fall through to rule-based

    # Rule-based fallback (AI disabled or failed)
    data = load_data()
    limits = data.get("category_limits", {})
    month_budget = data.get("monthly_budget", 0)
    month_spent = get_month_spent()

    batch_by_category = {}
    for item in item_results:
        cat = item["category"]
        batch_by_category[cat] = batch_by_category.get(cat, 0) + item["amount"]

    rule_reasons = []
    rule_approved = True

    if month_budget <= 0:
        rule_reasons.append("本月总预算未设置或为 0")
        rule_approved = False
    elif month_spent + total_amount > month_budget:
        rule_reasons.append(f"本次合计 {total_amount:.2f} 元，加上本月已用 {month_spent:.2f} 元将超出总预算 {month_budget:.2f} 元")
        rule_approved = False

    for cat, batch_amount in batch_by_category.items():
        cat_limit = limits.get(cat, 0)
        cat_spent = get_category_spent(cat)

        effective_cat_limit = min(cat_limit, month_budget) if cat_limit > 0 else 0
        if effective_cat_limit > 0 and cat_spent + batch_amount > effective_cat_limit:
            rule_reasons.append(f"【{cat}】分类本月已用 {cat_spent:.2f} 元，本次 {batch_amount:.2f} 元将超上限 {effective_cat_limit:.2f} 元")
            rule_approved = False

        # 行程审批跳过短时高频和1小时限制
        if not is_trip:
            cat_spent_recent = get_category_spent_recent(cat, hours=1)
            if effective_cat_limit > 0 and cat_spent_recent + batch_amount > effective_cat_limit:
                rule_reasons.append(f"【{cat}】最近1小时内已用 {cat_spent_recent:.2f} 元，本次 {batch_amount:.2f} 元将超上限 {effective_cat_limit:.2f} 元")
                rule_approved = False

            short_term_limit = month_budget * 0.15
            if cat_spent_recent + batch_amount > short_term_limit:
                rule_reasons.append(f"【{cat}】最近1小时内已用 {cat_spent_recent:.2f} 元，本次 {batch_amount:.2f} 元将超短时限额 {short_term_limit:.2f} 元")
                rule_approved = False

    if rule_approved and not rule_reasons:
        rule_reasons.append(f"本次消费合计 {total_amount:.2f} 元，余额充足，可以支出。")

    return {
        "approved": rule_approved,
        "reason": "；".join(rule_reasons),
        "total": total_amount,
        "items": item_results,
    }
