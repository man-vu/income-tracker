from __future__ import annotations

import csv
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, median, pstdev

from django.db.models import Sum


CATEGORY_RULES = {
    "Groceries": ["walmart", "costco", "loblaws", "grocery", "food basics"],
    "Transport": ["uber", "lyft", "transit", "metro", "gas"],
    "Entertainment": ["netflix", "spotify", "cinema", "movie", "steam"],
    "Utilities": ["hydro", "electric", "internet", "phone", "water"],
    "Rent": ["rent", "landlord", "mortgage"],
    "Dining": ["restaurant", "cafe", "coffee", "doordash", "ubereats"],
    "Savings": ["savings", "invest", "tfsa", "rrsp"],
}

DEFAULT_BUCKET_BY_CATEGORY = {
    "Groceries": "need",
    "Transport": "need",
    "Utilities": "need",
    "Rent": "need",
    "Healthcare": "need",
    "Dining": "want",
    "Entertainment": "want",
    "Shopping": "want",
    "Savings": "future",
    "Investment": "future",
    "Education": "future",
    "Emergency Fund": "future",
}


CATEGORY_NORMALIZATION = {
    "educaton": "Education",
    "education": "Education",
    "fod": "Food",
    "food": "Food",
    "rent": "Rent",
    "entertainment": "Entertainment",
    "freelance": "Freelance",
    "salary": "Salary",
    "groceries": "Groceries",
    "transport": "Transport",
    "utility": "Utilities",
    "utilities": "Utilities",
}


PAYMENT_MODE_TO_ACCOUNT_TYPE = {
    "card": "credit",
    "bank transfer": "checking",
    "bank": "checking",
    "cash": "cash",
}


MONEY_QUANT = Decimal("0.01")
MAX_MONEY = Decimal("99999999.99")


def infer_category(merchant: str, description: str) -> str:
    haystack = f"{merchant} {description}".lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "Uncategorized"


def month_window(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def forecast_month_end(expenses_qs, year: int, month: int) -> dict:
    first_day, last_day = month_window(year, month)
    month_total = float(expenses_qs.aggregate(total=Sum("amount"))["total"] or 0)
    today = date.today()
    if today < first_day:
        elapsed_days = 1
    elif today > last_day:
        elapsed_days = monthrange(year, month)[1]
    else:
        elapsed_days = today.day

    days_in_month = monthrange(year, month)[1]
    projection = month_total if elapsed_days <= 0 else (month_total / elapsed_days) * days_in_month

    return {
        "month_total": round(month_total, 2),
        "projected_total": round(projection, 2),
        "days_elapsed": elapsed_days,
        "days_in_month": days_in_month,
    }


def detect_budget_alerts(spend_by_category: dict, budgets) -> list[dict]:
    alerts = []
    for budget in budgets:
        spent = float(spend_by_category.get(budget.category, 0) or 0)
        limit = float(budget.monthly_limit)
        ratio = spent / limit if limit else 0
        alerts.append(
            {
                "category": budget.category,
                "spent": round(spent, 2),
                "limit": round(limit, 2),
                "ratio": ratio,
                "is_exceeded": ratio > 1,
            }
        )
    alerts.sort(key=lambda item: item["ratio"], reverse=True)
    return alerts


def detect_anomalies(expenses_qs) -> list[dict]:
    records = list(expenses_qs.order_by("-date")[:120])
    amounts = [float(item.amount) for item in records]
    if len(amounts) < 6:
        return []

    avg = mean(amounts)
    sigma = pstdev(amounts) or 1.0
    med = median(amounts)

    anomalies = []
    for expense in records:
        amount = float(expense.amount)
        z_score = (amount - avg) / sigma
        if z_score >= 2 or amount > med * 2.5:
            anomalies.append(
                {
                    "date": expense.date,
                    "category": expense.category,
                    "merchant": expense.merchant,
                    "amount": round(amount, 2),
                    "z_score": round(z_score, 2),
                }
            )
    return anomalies[:8]


def allocation_summary(expenses_qs, budgets) -> dict:
    bucket_by_category = {
        budget.category: budget.allocation_bucket for budget in budgets
    }
    totals = defaultdict(float)

    for expense in expenses_qs:
        category = expense.category or "Uncategorized"
        bucket = bucket_by_category.get(category) or DEFAULT_BUCKET_BY_CATEGORY.get(category, "want")
        totals[bucket] += float(expense.amount)

    total_spent = sum(totals.values()) or 1.0
    return {
        "need": {"amount": round(totals["need"], 2), "ratio": round(totals["need"] / total_spent * 100, 1)},
        "want": {"amount": round(totals["want"], 2), "ratio": round(totals["want"] / total_spent * 100, 1)},
        "future": {"amount": round(totals["future"], 2), "ratio": round(totals["future"] / total_spent * 100, 1)},
    }


def forecast_backtest(expenses_qs) -> dict:
    monthly_totals = list(
        expenses_qs.extra(select={"month": "strftime('%%Y-%%m', date)"})
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("-month")[:6]
    )

    if len(monthly_totals) < 3:
        return {"months_tested": 0, "avg_abs_error_pct": None}

    errors = []
    for row in monthly_totals[1:]:
        actual = float(row["total"] or 0)
        if actual == 0:
            continue
        prev = float(monthly_totals[0]["total"] or 0)
        err_pct = abs(prev - actual) / actual * 100
        errors.append(err_pct)

    if not errors:
        return {"months_tested": 0, "avg_abs_error_pct": None}

    return {"months_tested": len(errors), "avg_abs_error_pct": round(sum(errors) / len(errors), 1)}


def parse_dataset_date(raw_date: str) -> date | None:
    if not raw_date:
        return None

    raw_date = raw_date.strip()
    patterns = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d-%m-%y",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    for pattern in patterns:
        try:
            return date.fromisoformat(raw_date) if pattern == "%Y-%m-%d" else datetime.strptime(raw_date, pattern).date()
        except ValueError:
            continue
    return None


def normalize_category(raw: str) -> str:
    if not raw:
        return "Uncategorized"
    key = raw.strip().lower()
    normalized = CATEGORY_NORMALIZATION.get(key)
    if normalized:
        return normalized
    return raw.strip().title()


def normalize_payment_mode(raw: str) -> tuple[str, str]:
    value = (raw or "").strip().lower()
    if not value:
        value = "bank"

    account_type = PAYMENT_MODE_TO_ACCOUNT_TYPE.get(value, "checking")
    label = value.title()
    if label == "Csh":
        label = "Cash"
    return label, account_type


def import_budgetwise_dataset(user, csv_path: str | Path, clear_existing: bool = False) -> dict:
    from .models import Account, Expense, Income

    path = Path(csv_path)
    if not path.exists():
        return {"created_income": 0, "created_expense": 0, "skipped": 0, "error": f"Dataset not found: {path}"}

    if clear_existing:
        Income.objects.filter(user=user).delete()
        Expense.objects.filter(user=user).delete()

    created_income = 0
    created_expense = 0
    skipped = 0

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_type = (row.get("transaction_type") or "").strip().lower()
            amount_raw = (row.get("amount") or "").strip().replace(",", "")
            tx_date = parse_dataset_date((row.get("date") or "").strip())
            category = normalize_category(row.get("category") or "")
            location = (row.get("location") or "").strip()
            notes = (row.get("notes") or "").strip()
            payment_mode, account_type = normalize_payment_mode(row.get("payment_mode") or "")
            recurring_hint = notes.lower()
            is_recurring = any(token in recurring_hint for token in ["recurring", "monthly", "subscription"])

            try:
                amount = Decimal(amount_raw)
            except (InvalidOperation, TypeError):
                skipped += 1
                continue

            if not is_valid_money_amount(amount):
                skipped += 1
                continue

            if amount <= 0 or tx_type not in {"income", "expense"} or tx_date is None:
                skipped += 1
                continue

            account_name = f"Dataset {payment_mode}"
            account, _ = Account.objects.get_or_create(
                user=user,
                name=account_name,
                defaults={"account_type": account_type, "institution": "BudgetWise Import"},
            )

            if tx_type == "income":
                source = category if category != "Uncategorized" else (notes or "Dataset Income")
                exists = Income.objects.filter(user=user, amount=amount, source=source, date=tx_date).exists()
                if exists:
                    skipped += 1
                    continue

                Income.objects.create(
                    user=user,
                    account=account,
                    amount=amount,
                    source=source,
                    date=tx_date,
                    is_recurring=is_recurring,
                )
                created_income += 1
            else:
                merchant = location or "Unknown"
                exists = Expense.objects.filter(
                    user=user,
                    amount=amount,
                    category=category,
                    merchant=merchant,
                    date=tx_date,
                ).exists()
                if exists:
                    skipped += 1
                    continue

                Expense.objects.create(
                    user=user,
                    account=account,
                    amount=amount,
                    category=category,
                    merchant=merchant,
                    date=tx_date,
                    description=notes,
                    is_recurring=is_recurring,
                )
                created_expense += 1

    return {
        "created_income": created_income,
        "created_expense": created_expense,
        "skipped": skipped,
        "error": None,
    }


def is_valid_money_amount(amount: Decimal) -> bool:
    if amount is None:
        return False
    if amount <= 0 or amount > MAX_MONEY:
        return False
    try:
        amount.quantize(MONEY_QUANT)
    except InvalidOperation:
        return False
    return True


def cleanup_invalid_amount_rows(user) -> dict:
    from django.db import connection

    from .models import Expense, Income

    invalid_income_ids = []
    invalid_expense_ids = []

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, amount FROM tracker_income WHERE user_id = %s", [user.id])
        for row_id, raw_amount in cursor.fetchall():
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, TypeError):
                invalid_income_ids.append(row_id)
                continue
            if not is_valid_money_amount(amount):
                invalid_income_ids.append(row_id)

        cursor.execute("SELECT id, amount FROM tracker_expense WHERE user_id = %s", [user.id])
        for row_id, raw_amount in cursor.fetchall():
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, TypeError):
                invalid_expense_ids.append(row_id)
                continue
            if not is_valid_money_amount(amount):
                invalid_expense_ids.append(row_id)

    if invalid_income_ids:
        Income.objects.filter(id__in=invalid_income_ids).delete()
    if invalid_expense_ids:
        Expense.objects.filter(id__in=invalid_expense_ids).delete()

    return {
        "removed_income": len(invalid_income_ids),
        "removed_expense": len(invalid_expense_ids),
    }
