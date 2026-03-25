from django.contrib.auth.models import User
from django.db import models


class Income(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    dataset_user_id = models.IntegerField(null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=100)
    date = models.DateField()

    def __str__(self):
        return f"{self.source}: ${self.amount}"


class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    dataset_user_id = models.IntegerField(null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100)
    date = models.DateField()

    def __str__(self):
        return f"{self.category}: ${self.amount}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    dataset_user_id = models.IntegerField(null=True, blank=True)
    category = models.CharField(max_length=100)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.category}: ${self.monthly_limit}"
