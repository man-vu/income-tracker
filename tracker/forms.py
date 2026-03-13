from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Account, CategoryBudget, Expense, Goal, Income
from .services import infer_category
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['amount', 'source', 'date', 'account', 'is_recurring']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['account'].queryset = Account.objects.filter(user=self.user)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('Amount must be greater than 0.')
        return amount

    def clean_date(self):
        tx_date = self.cleaned_data['date']
        if tx_date > timezone.localdate():
            raise ValidationError('Date cannot be in the future.')
        return tx_date

    def clean(self):
        cleaned_data = super().clean()
        if not self.user:
            return cleaned_data

        amount = cleaned_data.get('amount')
        tx_date = cleaned_data.get('date')
        source = cleaned_data.get('source')
        if amount and tx_date and source:
            duplicate = Income.objects.filter(
                user=self.user,
                amount=amount,
                date=tx_date,
                source__iexact=source,
            ).exists()
            if duplicate:
                raise ValidationError('A similar income record already exists for this date.')
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['amount', 'category', 'merchant', 'date', 'description', 'account', 'is_recurring', 'is_transfer']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['account'].queryset = Account.objects.filter(user=self.user)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('Amount must be greater than 0.')
        return amount

    def clean_date(self):
        tx_date = self.cleaned_data['date']
        if tx_date > timezone.localdate():
            raise ValidationError('Date cannot be in the future.')
        return tx_date

    def clean(self):
        cleaned_data = super().clean()
        if not self.user:
            return cleaned_data

        merchant = cleaned_data.get('merchant') or ''
        description = cleaned_data.get('description') or ''
        category = cleaned_data.get('category')
        if not category:
            cleaned_data['category'] = infer_category(merchant, description)

        amount = cleaned_data.get('amount')
        tx_date = cleaned_data.get('date')
        if amount and tx_date:
            duplicate = Expense.objects.filter(
                user=self.user,
                amount=amount,
                date=tx_date,
                merchant__iexact=merchant,
            ).exists()
            if duplicate:
                raise ValidationError('A similar expense record already exists for this date.')

        return cleaned_data


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['name', 'monthly_goal', 'target_amount', 'current_amount', 'deadline']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'})
        }

    def clean(self):
        cleaned_data = super().clean()
        target = cleaned_data.get('target_amount')
        current = cleaned_data.get('current_amount')
        deadline = cleaned_data.get('deadline')

        if target is not None and target <= 0:
            raise ValidationError('Target amount must be greater than 0.')
        if current is not None and current < 0:
            raise ValidationError('Current amount cannot be negative.')
        if deadline and deadline < timezone.localdate():
            raise ValidationError('Deadline must be today or a future date.')
        return cleaned_data


class CategoryBudgetForm(forms.ModelForm):
    class Meta:
        model = CategoryBudget
        fields = ['category', 'monthly_limit', 'allocation_bucket']

    def clean_monthly_limit(self):
        monthly_limit = self.cleaned_data['monthly_limit']
        if monthly_limit <= 0:
            raise ValidationError('Monthly limit must be greater than 0.')
        return monthly_limit


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'account_type', 'institution', 'credit_limit']

    def clean_credit_limit(self):
        credit_limit = self.cleaned_data.get('credit_limit')
        if credit_limit is not None and credit_limit <= 0:
            raise ValidationError('Credit limit must be greater than 0 if provided.')
        return credit_limit