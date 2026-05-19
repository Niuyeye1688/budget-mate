#!/usr/bin/env python3
import sys
import io

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import re
from budget import (
    set_monthly_budget,
    get_monthly_budget,
    set_category_limit,
    get_category_limits,
    get_remaining_budget,
)
from approver import judge_expense, detect_category
from ledger import add_record, get_all_records, get_month_spent, get_category_spent
from bills import generate_daily_bill, generate_weekly_bill, export_bill


HELP_TEXT = """
💰 经费审批与记账助手

命令列表:
  设置预算 <金额>          — 设置本月总预算
  设置上限 <分类> <金额>   — 设置某分类的月度上限
  查看预算                 — 显示当前预算和余额
  审批 <金额> <用途>       — 提交一笔支出请求，AI 判断是否可花
  直接记 <金额> <用途>     — 跳过审批直接记账（默认通过）
  记录                     — 查看所有记账记录
  今日账单                 — 生成今日账单
  本周账单                 — 生成本周账单
  导出账单                 — 导出最近一张账单到文件
  帮助                     — 显示本帮助
  退出                     — 退出程序

示例:
  审批 200 请朋友吃饭
  设置预算 5000
  设置上限 餐饮 1500
"""


def parse_amount(text):
    text = text.replace("元", "").replace("块", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def cmd_set_budget(parts):
    if len(parts) < 2:
        print("用法: 设置预算 <金额>")
        return
    amount = parse_amount(parts[1])
    if amount is None:
        print("请输入有效的金额数字")
        return
    set_monthly_budget(amount)
    print(f"[OK] 本月总预算已设置为 {amount:.2f} 元")


def cmd_set_limit(parts):
    if len(parts) < 3:
        print("用法: 设置上限 <分类> <金额>")
        print(f"可选分类: {', '.join(get_category_limits().keys())}")
        return
    category = parts[1]
    amount = parse_amount(parts[2])
    if amount is None:
        print("请输入有效的金额数字")
        return
    set_category_limit(category, amount)
    print(f"[OK] 【{category}】月度上限已设置为 {amount:.2f} 元")


def cmd_view_budget():
    budget = get_monthly_budget()
    spent = get_month_spent()
    remaining = get_remaining_budget()
    limits = get_category_limits()
    print(f"\n[总预算] 本月总预算: {budget:.2f} 元")
    print(f"[已用]   本月已用:   {spent:.2f} 元")
    print(f"[剩余]   本月剩余:   {remaining:.2f} 元\n")
    print("[分类] 分类预算上限:")
    for cat, limit in limits.items():
        cat_spent = get_category_spent(cat)
        if limit > 0:
            pct = (cat_spent / limit) * 100 if limit else 0
            print(f"   {cat}: {cat_spent:.2f} / {limit:.2f} 元 ({pct:.1f}%)")
        else:
            print(f"   {cat}: {cat_spent:.2f} / 未设置 元")
    print()


def cmd_approve(parts):
    if len(parts) < 3:
        print("用法: 审批 <金额> <用途>")
        return
    amount = parse_amount(parts[1])
    if amount is None:
        print("请输入有效的金额数字")
        return
    description = " ".join(parts[2:])
    result = judge_expense(amount, description)
    cat = result["category"]

    if result["approved"]:
        print(f"\n[批准] 这笔 {amount:.2f} 元的支出可以通过")
        print(f"   分类: {cat}")
        print(f"   理由: {result['reason']}")
        add_record(amount, description, cat, approved=True)
        print("   已自动记账。\n")
    else:
        print(f"\n[拒绝] 这笔 {amount:.2f} 元的支出不建议花")
        print(f"   分类: {cat}")
        print(f"   理由: {result['reason']}")
        add_record(amount, description, cat, approved=False)
        print("   已记录为拒绝。\n")


def cmd_direct_record(parts):
    if len(parts) < 3:
        print("用法: 直接记 <金额> <用途>")
        return
    amount = parse_amount(parts[1])
    if amount is None:
        print("请输入有效的金额数字")
        return
    description = " ".join(parts[2:])
    cat = detect_category(description)
    add_record(amount, description, cat, approved=True)
    print(f"[OK] 已直接记账: {amount:.2f} 元 | {cat} | {description}")


def cmd_records():
    records = get_all_records()
    if not records:
        print("暂无记录")
        return
    print(f"\n[记录] 全部记录 ({len(records)} 条):")
    for r in records[-20:]:
        status = "[通过]" if r["approved"] else "[拒绝]"
        print(f"  [{r['id']}] {r['date']} | {r['amount']:.2f} 元 | {r['category']} | {r['description']} {status}")
    if len(records) > 20:
        print(f"  ... 还有 {len(records) - 20} 条更早的记录")
    print()


def main():
    print("=" * 50)
    print("[经费助手] 欢迎使用经费审批与记账助手")
    print("=" * 50)
    print("输入 '帮助' 查看命令列表\n")

    last_bill = None

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()

        if cmd in ("退出", "quit", "exit", "q"):
            print("再见!")
            break

        elif cmd in ("帮助", "help", "h", "?"):
            print(HELP_TEXT)

        elif cmd == "设置预算":
            cmd_set_budget(parts)

        elif cmd == "设置上限":
            cmd_set_limit(parts)

        elif cmd == "查看预算":
            cmd_view_budget()

        elif cmd in ("审批", "approve"):
            cmd_approve(parts)

        elif cmd == "直接记":
            cmd_direct_record(parts)

        elif cmd in ("记录", "records"):
            cmd_records()

        elif cmd == "今日账单":
            bill = generate_daily_bill()
            print("\n" + bill)
            last_bill = ("每日账单", bill)

        elif cmd == "本周账单":
            bill = generate_weekly_bill()
            print("\n" + bill)
            last_bill = ("每周账单", bill)

        elif cmd == "导出账单":
            if last_bill is None:
                print("请先生成一张账单（今日账单 / 本周账单）")
            else:
                name, content = last_bill
                fname = export_bill(content)
                print(f"[OK] {name} 已导出到文件: {fname}")

        else:
            print("未知命令，输入 '帮助' 查看可用命令。")


if __name__ == "__main__":
    main()
