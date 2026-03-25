from django.contrib import admin

from .models import Budget, Expense, Income

admin.site.register(Income)
admin.site.register(Expense)
admin.site.register(Budget)
