import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BudgetForm, ExpenseForm, IncomeForm
from .models import Budget, Expense, Income


def get_dataset_user_id(request):
    """Return the dataset user_id stored in the session, or None."""
    uid = request.session.get("dataset_user_id")
    return int(uid) if uid else None


def ensure_dataset_loaded():
    """Import the CSV dataset if the database is empty."""
    if Income.objects.filter(dataset_user_id__isnull=False).exists():
        return

    csv_path = Path(settings.BASE_DIR) / "personal_finance_tracker_dataset.csv"
    if not csv_path.exists():
        return

    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tx_date = parse_date(row.get("date") or "")
            category = (row.get("category") or "Uncategorized").strip().title()
            income_type = (row.get("income_type") or "Income").strip()
            csv_user_id = row.get("user_id", "").strip()

            if tx_date is None or not csv_user_id.isdigit():
                continue

            try:
                income_amt = Decimal(row.get("monthly_income") or "0")
                expense_amt = Decimal(row.get("monthly_expense_total") or "0")
            except InvalidOperation:
                continue

            uid = int(csv_user_id)

            if income_amt > 0:
                Income.objects.create(
                    dataset_user_id=uid, amount=income_amt,
                    source=income_type, date=tx_date,
                )
            if expense_amt > 0:
                Expense.objects.create(
                    dataset_user_id=uid, amount=expense_amt,
                    category=category, date=tx_date,
                )


def select_user(request):
    """Simple form: enter a dataset user_id to view their finances."""
    if request.method == "POST":
        uid = request.POST.get("user_id", "").strip()
        if uid.isdigit():
            ensure_dataset_loaded()
            request.session["dataset_user_id"] = int(uid)
            return redirect("dashboard")
        messages.error(request, "Please enter a valid numeric user ID.")
    return render(request, "select_user.html")


def logout_user(request):
    """Clear the selected user from session."""
    request.session.flush()
    return redirect("select_user")


def dashboard(request):
    uid = get_dataset_user_id(request)
    if not uid:
        return redirect("select_user")

    month = request.GET.get("month")
    year = request.GET.get("year")

    incomes = Income.objects.filter(dataset_user_id=uid)
    expenses = Expense.objects.filter(dataset_user_id=uid)

    if month and year:
        incomes = incomes.filter(date__year=year, date__month=month)
        expenses = expenses.filter(date__year=year, date__month=month)

    total_income = incomes.aggregate(Sum("amount"))["amount__sum"] or 0
    total_expense = expenses.aggregate(Sum("amount"))["amount__sum"] or 0
    net_savings = total_income - total_expense

    # Category breakdown for the pie chart
    category_data = expenses.values("category").annotate(total=Sum("amount"))
    categories = [row["category"] for row in category_data]
    category_totals = [float(row["total"]) for row in category_data]

    # Budget alerts: compare spending vs limits
    budgets = Budget.objects.filter(dataset_user_id=uid)
    spent_by_category = {row["category"]: row["total"] for row in category_data}
    budget_alerts = []
    for budget in budgets:
        spent = float(spent_by_category.get(budget.category, 0))
        limit = float(budget.monthly_limit)
        budget_alerts.append({
            "category": budget.category,
            "spent": spent,
            "limit": limit,
            "exceeded": spent > limit,
        })

    context = {
        "dataset_user_id": uid,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_savings": net_savings,
        "categories": categories,
        "category_totals": category_totals,
        "budget_alerts": budget_alerts,
        "recent_incomes": incomes.order_by("-date")[:5],
        "recent_expenses": expenses.order_by("-date")[:5],
    }
    return render(request, "dashboard.html", context)


def add_income(request):
    uid = get_dataset_user_id(request)
    if not uid:
        return redirect("select_user")

    form = IncomeForm(request.POST or None)
    if form.is_valid():
        income = form.save(commit=False)
        income.dataset_user_id = uid
        income.save()
        messages.success(request, "Income added.")
        return redirect("dashboard")
    return render(request, "add_income.html", {"form": form})


def add_expense(request):
    uid = get_dataset_user_id(request)
    if not uid:
        return redirect("select_user")

    form = ExpenseForm(request.POST or None)
    if form.is_valid():
        expense = form.save(commit=False)
        expense.dataset_user_id = uid
        expense.save()
        messages.success(request, "Expense added.")
        return redirect("dashboard")
    return render(request, "add_expense.html", {"form": form})


def manage_budgets(request):
    uid = get_dataset_user_id(request)
    if not uid:
        return redirect("select_user")

    form = BudgetForm(request.POST or None)
    if form.is_valid():
        budget = form.save(commit=False)
        budget.dataset_user_id = uid
        budget.save()
        messages.success(request, "Budget saved.")
        return redirect("manage_budgets")
    budgets = Budget.objects.filter(dataset_user_id=uid).order_by("category")
    return render(request, "manage_budgets.html", {"form": form, "budgets": budgets})


def delete_budget(request, budget_id):
    uid = get_dataset_user_id(request)
    if not uid:
        return redirect("select_user")

    budget = get_object_or_404(Budget, id=budget_id, dataset_user_id=uid)
    if request.method == "POST":
        budget.delete()
        messages.info(request, "Budget deleted.")
    return redirect("manage_budgets")


def parse_date(raw):
    """Try multiple date formats from the dataset."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


