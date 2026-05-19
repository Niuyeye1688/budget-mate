import json
import urllib.request
from storage import load_data, get_current_month
from ledger import get_month_spent, get_category_spent, get_category_spent_recent, get_recent_records


def detect_category(description):
    desc = description.lower()
    keywords = {
        "餐饮": ["饭", "餐", "吃", "餐厅", "食堂", "外卖", "火锅", "烧烤", "咖啡", "奶茶", "菜", "请客", "聚餐", "酒", "食"],
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

    reasons = []
    approved = True

    if month_budget <= 0:
        reasons.append("本月总预算未设置或为 0")
        approved = False
    elif month_spent + amount > month_budget:
        reasons.append(f"本月已用 {month_spent:.2f} 元，加上这笔 {amount:.2f} 元将超出总预算 {month_budget:.2f} 元")
        approved = False

    if cat_limit > 0 and cat_spent + amount > cat_limit:
        reasons.append(f"【{category}】分类本月已用 {cat_spent:.2f} 元，上限为 {cat_limit:.2f} 元")
        approved = False

    if cat_limit > 0 and cat_spent_recent + amount > cat_limit:
        reasons.append(f"【{category}】最近1小时内已用 {cat_spent_recent:.2f} 元，加上这笔将超上限 {cat_limit:.2f} 元")
        approved = False

    return approved, reasons, category


def ai_judge(amount, description, recent_items=None, recent_total=0):
    data = load_data()
    config = data.get("api_config", {})
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "https://api.deepseek.com")
    model = config.get("model", "deepseek-chat")

    month_budget = data.get("monthly_budget", 0)
    month_spent = get_month_spent()
    remaining = month_budget - month_spent

    cat_info = []
    for cat, limit in data.get("category_limits", {}).items():
        spent = get_category_spent(cat)
        recent = get_category_spent_recent(cat, hours=1)
        if limit > 0:
            cat_info.append(f"{cat}: 本月已用{spent:.0f}元/上限{limit:.0f}元，最近1小时已用{recent:.0f}元")
        else:
            cat_info.append(f"{cat}: 本月已用{spent:.0f}元/无上限，最近1小时已用{recent:.0f}元")

    cat_text = "；".join(cat_info) if cat_info else "暂无分类预算"

    # 构建"本次外出"消费上下文
    recent_context = ""
    if recent_items:
        lines = "\n".join([f"- {item['description']} {item['amount']:.0f}元" for item in recent_items])
        total_with_current = recent_total + amount
        recent_context = f"""\n本次外出您在同分类已消费：
{lines}
加上这笔【{description}】{amount:.0f}元，本次外出合计 {total_with_current:.0f} 元。\n"""

    prompt = f"""你是严格的私人财务顾问，用户花钱前必须经你审批。你的原则是帮用户省钱，对非必要支出要果断拒绝。

用户当前财务状况：
- 月预算：{month_budget:.0f}元
- 本月已用：{month_spent:.0f}元
- 本月剩余：{remaining:.0f}元
- 各分类使用情况：{cat_text}

用户申请支出：{amount:.0f}元
用途描述：{description}
{recent_context}
判断标准（严格执行）：
1. 余额不足或分类将超支 → 必须拒绝
2. 餐饮类：正常一餐 50-150 元，超过 200 元属于高消费，超过 300 元除非特殊场合（如请客、聚餐）否则拒绝。如果最近30分钟内有其他餐饮消费，应合并视为"本次一餐"判断
3. 交通类：日常通勤单次不应超过 100 元，打车非急事应拒绝。如果最近30分钟内有其他交通消费，应合并视为"本次出行"判断
4. 购物类：非必需品优先拒绝，奢侈品直接拒绝
5. 娱乐类：每月不超过 2-3 次，单次不超过预算 10%
6. 明显浪费、冲动消费、可替代方案更便宜的 → 拒绝

请根据用途描述判断属于哪个分类（餐饮/交通/购物/娱乐/其他）。
输出严格JSON，不要有任何其他文字：
{{"approved": true/false, "reason": "简短理由（不超过30字）", "category": "分类名"}}"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严格的私人财务顾问，帮助用户控制支出。输出必须是JSON格式。"},
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


def judge_expense(amount, description):
    data = load_data()
    config = data.get("api_config", {})

    ai_result = None
    category = detect_category(description)

    # 获取最近30分钟同分类已批准消费（用于智能外出合并）
    recent_items = get_recent_records(category, minutes=30)
    recent_total = sum(item["amount"] for item in recent_items)

    # Try AI judgment if enabled
    if config.get("enabled") and config.get("api_key"):
        try:
            ai_result = ai_judge(amount, description, recent_items=recent_items, recent_total=recent_total)
            category = ai_result.get("category", category)
        except Exception:
            pass  # AI failed, fall through to rule-based only

    # Rule-based guardrails (always enforce budget limits + time window)
    rule_approved, rule_reasons, category = _check_rules(amount, category)

    # Build final result
    trip_prefix = ""
    if recent_items:
        trip_total = recent_total + amount
        trip_prefix = f"本次外出【{category}】合计 {trip_total:.2f} 元（含之前已审批的 {recent_total:.2f} 元）。"

    if ai_result is not None:
        # AI gave an opinion, but rules override
        if not rule_approved:
            all_reasons = []
            if trip_prefix:
                all_reasons.append(trip_prefix)
            if ai_result.get("reason"):
                all_reasons.append(f"AI判断：{ai_result['reason']}")
            all_reasons.extend(rule_reasons)
            return {
                "approved": False,
                "category": category,
                "reason": "；".join(all_reasons),
            }
        else:
            # Rules pass, respect AI decision
            reason = ai_result.get("reason", "AI判断通过")
            if trip_prefix:
                reason = trip_prefix + reason
            return {
                "approved": ai_result.get("approved", True),
                "category": category,
                "reason": reason,
            }
    else:
        # Pure rule-based (no AI or AI failed)
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


def judge_batch_expense(items):
    """
    批量审批。items = [{"amount": 15, "description": "午饭"}, ...]
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

    # 合并同分类金额进行规则检查
    data = load_data()
    limits = data.get("category_limits", {})
    month_budget = data.get("monthly_budget", 0)
    month_spent = get_month_spent()

    # 按分类合并本次批量金额
    batch_by_category = {}
    for item in item_results:
        cat = item["category"]
        batch_by_category[cat] = batch_by_category.get(cat, 0) + item["amount"]

    rule_reasons = []
    rule_approved = True

    # 检查总预算
    if month_budget <= 0:
        rule_reasons.append("本月总预算未设置或为 0")
        rule_approved = False
    elif month_spent + total_amount > month_budget:
        rule_reasons.append(f"本次合计 {total_amount:.2f} 元，加上本月已用 {month_spent:.2f} 元将超出总预算 {month_budget:.2f} 元")
        rule_approved = False

    # 检查各分类上限（本月累计 + 批量金额 + 最近1小时）
    for cat, batch_amount in batch_by_category.items():
        cat_limit = limits.get(cat, 0)
        cat_spent = get_category_spent(cat)
        cat_spent_recent = get_category_spent_recent(cat, hours=1)

        if cat_limit > 0 and cat_spent + batch_amount > cat_limit:
            rule_reasons.append(f"【{cat}】分类本月已用 {cat_spent:.2f} 元，本次 {batch_amount:.2f} 元将超上限 {cat_limit:.2f} 元")
            rule_approved = False

        if cat_limit > 0 and cat_spent_recent + batch_amount > cat_limit:
            rule_reasons.append(f"【{cat}】最近1小时内已用 {cat_spent_recent:.2f} 元，本次 {batch_amount:.2f} 元将超上限 {cat_limit:.2f} 元")
            rule_approved = False

    # AI 判断（用合并描述）
    ai_result = None
    config = data.get("api_config", {})
    if config.get("enabled") and config.get("api_key"):
        try:
            ai_result = ai_judge(total_amount, f"本次外出消费：{combined_desc}")
        except Exception:
            pass

    # 组装结果
    if ai_result is not None:
        if not rule_approved:
            all_reasons = []
            if ai_result.get("reason"):
                all_reasons.append(f"AI判断：{ai_result['reason']}")
            all_reasons.extend(rule_reasons)
            return {
                "approved": False,
                "reason": "；".join(all_reasons),
                "total": total_amount,
                "items": item_results,
            }
        else:
            return {
                "approved": ai_result.get("approved", True),
                "reason": ai_result.get("reason", "AI判断通过"),
                "total": total_amount,
                "items": item_results,
            }
    else:
        if rule_approved and not rule_reasons:
            rule_reasons.append(f"本次消费合计 {total_amount:.2f} 元，余额充足，可以支出。")

        return {
            "approved": rule_approved,
            "reason": "；".join(rule_reasons),
            "total": total_amount,
            "items": item_results,
        }
