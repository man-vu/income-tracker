from django import forms

from .models import Budget, Expense, Income


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ["amount", "source", "date"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["amount", "category", "date"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["category", "monthly_limit"]
