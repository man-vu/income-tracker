from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("select-user/", views.select_user, name="select_user"),
    path("logout/", views.logout_user, name="logout_user"),
    path("add-income/", views.add_income, name="add_income"),
    path("add-expense/", views.add_expense, name="add_expense"),
    path("budgets/", views.manage_budgets, name="manage_budgets"),
    path("budgets/<int:budget_id>/delete/", views.delete_budget, name="delete_budget"),
]
