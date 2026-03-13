from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add-income/', views.add_income, name='add_income'),
    path('add-expense/', views.add_expense, name='add_expense'),
    path('goals/', views.manage_goals, name='manage_goals'),
    path('goals/<int:goal_id>/delete/', views.delete_goal, name='delete_goal'),
    path('budgets/', views.manage_budgets, name='manage_budgets'),
    path('budgets/<int:budget_id>/delete/', views.delete_budget, name='delete_budget'),
    path('accounts/', views.manage_accounts, name='manage_accounts'),
    path('accounts/<int:account_id>/delete/', views.delete_account, name='delete_account'),
    path('import-dataset/', views.import_dataset, name='import_dataset'),
    path('register/', views.register, name='register'),

]