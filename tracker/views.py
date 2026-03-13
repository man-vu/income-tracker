from calendar import month_name
from datetime import date
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AccountForm, CategoryBudgetForm, ExpenseForm, GoalForm, IncomeForm, RegisterForm
from .models import Account, CategoryBudget, Expense, Goal, Income
from .services import allocation_summary, cleanup_invalid_amount_rows, detect_anomalies, detect_budget_alerts, forecast_backtest, forecast_month_end, import_budgetwise_dataset


@login_required
def dashboard(request):
    cleanup_result = cleanup_invalid_amount_rows(request.user)
    removed_total = cleanup_result["removed_income"] + cleanup_result["removed_expense"]
    if removed_total:
        messages.warning(request, f"Removed {removed_total} invalid transaction row(s) with malformed amounts.")

    today = date.today()
    latest_income_date = Income.objects.filter(user=request.user).order_by("-date").values_list("date", flat=True).first()
    latest_expense_date = Expense.objects.filter(user=request.user).order_by("-date").values_list("date", flat=True).first()
    latest_data_date = max([d for d in [latest_income_date, latest_expense_date] if d], default=today)

    month_param = request.GET.get("month")
    year_param = request.GET.get("year")
    try:
        month = int(month_param) if month_param else latest_data_date.month
    except (TypeError, ValueError):
        month = latest_data_date.month
    try:
        year = int(year_param) if year_param else latest_data_date.year
    except (TypeError, ValueError):
        year = latest_data_date.year

    incomes = Income.objects.filter(user=request.user, date__year=year, date__month=month)
    expenses = Expense.objects.filter(user=request.user, date__year=year, date__month=month)
    all_expenses = Expense.objects.filter(user=request.user)

    total_income = incomes.aggregate(Sum("amount"))["amount__sum"] or 0
    total_expense = expenses.aggregate(Sum("amount"))["amount__sum"] or 0
    savings = total_income - total_expense

    recent_incomes = incomes.order_by("-created_at")[:5]
    recent_expenses = expenses.order_by("-created_at")[:5]

    category_data = expenses.values("category").annotate(total=Sum("amount"))
    categories = [item["category"] for item in category_data]
    category_totals = [float(item["total"]) for item in category_data]

    budgets = CategoryBudget.objects.filter(user=request.user).order_by("category")
    spend_by_category = {item["category"]: item["total"] for item in category_data}
    budget_alerts = detect_budget_alerts(spend_by_category, budgets)
    anomalies = detect_anomalies(all_expenses)
    forecast = forecast_month_end(expenses, year, month)
    backtest = forecast_backtest(all_expenses)
    allocations = allocation_summary(expenses, budgets)

    goals = Goal.objects.filter(user=request.user).order_by("deadline")
    goal_rows = []
    for goal in goals:
        progress_pct = 0
        if goal.target_amount:
            progress_pct = float(goal.current_amount / goal.target_amount * 100)
        goal_rows.append(
            {
                "name": goal.name,
                "current": float(goal.current_amount),
                "target": float(goal.target_amount),
                "monthly_goal": float(goal.monthly_goal),
                "deadline": goal.deadline,
                "progress_pct": min(round(progress_pct, 1), 100),
            }
        )

    monthly_options = [{"value": idx, "label": month_name[idx]} for idx in range(1, 13)]
    year_options = list(range(today.year - 2, today.year + 1))

    context = {
        "total_income": total_income,
        "total_expense": total_expense,
        "savings": savings,
        "recent_incomes": recent_incomes,
        "recent_expenses": recent_expenses,
        "categories": categories,
        "category_totals": category_totals,
        "budget_alerts": budget_alerts,
        "anomalies": anomalies,
        "forecast": forecast,
        "backtest": backtest,
        "allocations": allocations,
        "goals": goal_rows,
        "month": month,
        "year": year,
        "monthly_options": monthly_options,
        "year_options": year_options,
    }
    return render(request, "dashboard.html", context)


@login_required
def add_income(request):
    if request.method == "POST":
        form = IncomeForm(request.POST, user=request.user)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            messages.success(request, "Income saved.")
            return redirect("dashboard")
    else:
        form = IncomeForm(user=request.user)

    return render(request, "add_income.html", {"form": form})


@login_required
def add_expense(request):
    if request.method == "POST":
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, "Expense saved.")
            return redirect("dashboard")
    else:
        form = ExpenseForm(user=request.user)
    return render(request, "add_expense.html", {"form": form})


@login_required
def manage_goals(request):
    if request.method == "POST":
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, "Goal saved.")
            return redirect("manage_goals")
    else:
        form = GoalForm()

    goals = Goal.objects.filter(user=request.user).order_by("deadline")
    return render(request, "manage_goals.html", {"form": form, "goals": goals})


@login_required
def delete_goal(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    if request.method == "POST":
        goal.delete()
        messages.info(request, "Goal deleted.")
    return redirect("manage_goals")


@login_required
def manage_budgets(request):
    if request.method == "POST":
        form = CategoryBudgetForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            CategoryBudget.objects.update_or_create(
                user=request.user,
                category=cleaned["category"],
                defaults={
                    "monthly_limit": cleaned["monthly_limit"],
                    "allocation_bucket": cleaned["allocation_bucket"],
                },
            )
            messages.success(request, "Budget saved.")
            return redirect("manage_budgets")
    else:
        form = CategoryBudgetForm()

    budgets = CategoryBudget.objects.filter(user=request.user).order_by("category")
    return render(request, "manage_budgets.html", {"form": form, "budgets": budgets})


@login_required
def delete_budget(request, budget_id):
    budget = get_object_or_404(CategoryBudget, id=budget_id, user=request.user)
    if request.method == "POST":
        budget.delete()
        messages.info(request, "Budget deleted.")
    return redirect("manage_budgets")


@login_required
def manage_accounts(request):
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            messages.success(request, "Account saved.")
            return redirect("manage_accounts")
    else:
        form = AccountForm()

    accounts = Account.objects.filter(user=request.user).order_by("name")
    return render(request, "manage_accounts.html", {"form": form, "accounts": accounts})


@login_required
def delete_account(request, account_id):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    if request.method == "POST":
        account.delete()
        messages.info(request, "Account deleted.")
    return redirect("manage_accounts")


@login_required
def import_dataset(request):
    if request.method != "POST":
        return redirect("dashboard")

    dataset_path = Path(settings.BASE_DIR) / "data" / "budgetwise_finance_dataset.csv"
    clear_existing = request.POST.get("clear_existing") == "1"

    result = import_budgetwise_dataset(request.user, dataset_path, clear_existing=clear_existing)
    if result["error"]:
        messages.error(request, result["error"])
    else:
        messages.success(
            request,
            f"Dataset imported. Income: {result['created_income']}, Expense: {result['created_expense']}, Skipped: {result['skipped']}.",
        )
    return redirect("dashboard")


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "register.html", {"form": form})


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")