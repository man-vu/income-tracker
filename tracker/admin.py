from django.contrib import admin

from .models import Account, CategoryBudget, Expense, Goal, Income

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'source', 'account', 'is_recurring', 'date')
    list_filter = ('date', 'source', 'is_recurring')
    search_fields = ('user__username', 'source')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'merchant', 'amount', 'account', 'is_recurring', 'is_transfer', 'date')
    list_filter = ('date', 'category', 'is_recurring', 'is_transfer')
    search_fields = ('user__username', 'category', 'merchant')

@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'monthly_goal', 'target_amount', 'current_amount', 'deadline')


@admin.register(CategoryBudget)
class CategoryBudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'monthly_limit', 'allocation_bucket')
    list_filter = ('allocation_bucket',)
    search_fields = ('user__username', 'category')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'account_type', 'institution', 'credit_limit')
    list_filter = ('account_type',)
    search_fields = ('user__username', 'name', 'institution')

#admin.site.register(Income, IncomeAdmin)
#admin.site.register(Income)
#admin.site.register(Expense)
#admin.site.register(Goal)