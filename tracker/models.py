from django.contrib.auth.models import User
from django.db import models


ALLOCATION_BUCKETS = [
    ("need", "Need"),
    ("want", "Want"),
    ("future", "Future"),
]


ACCOUNT_TYPES = [
    ("checking", "Checking"),
    ("savings", "Savings"),
    ("credit", "Credit"),
    ("cash", "Cash"),
]


class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    institution = models.CharField(max_length=120, blank=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("user", "name")

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

class Income(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=100)
    date = models.DateField()
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.amount}"

class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True, default="Uncategorized")
    merchant = models.CharField(max_length=120, blank=True, default="")
    date = models.DateField()
    is_recurring = models.BooleanField(default=False)
    is_transfer = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"

class Goal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=120, default="Savings Goal")
    monthly_goal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deadline = models.DateField()

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class CategoryBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=100)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)
    allocation_bucket = models.CharField(max_length=10, choices=ALLOCATION_BUCKETS, default="need")

    class Meta:
        unique_together = ("user", "category")

    def __str__(self):
        return f"{self.category}: {self.monthly_limit}"