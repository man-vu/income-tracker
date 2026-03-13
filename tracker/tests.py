from django.test import TestCase
from django.contrib.auth.models import User
from pathlib import Path
import tempfile

from .models import CategoryBudget, Expense, Income
from .services import detect_budget_alerts, forecast_month_end, import_budgetwise_dataset, infer_category


class AnalyticsServiceTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="demo", password="password123")

	def test_infer_category_matches_keyword(self):
		category = infer_category("Uber Trip", "Ride to school")
		self.assertEqual(category, "Transport")

	def test_detect_budget_alerts_marks_exceeded(self):
		budget = CategoryBudget.objects.create(
			user=self.user,
			category="Groceries",
			monthly_limit=100,
			allocation_bucket="need",
		)
		alerts = detect_budget_alerts({"Groceries": 125}, [budget])
		self.assertEqual(len(alerts), 1)
		self.assertTrue(alerts[0]["is_exceeded"])

	def test_forecast_month_end_returns_projection(self):
		Expense.objects.create(
			user=self.user,
			amount=50,
			category="Groceries",
			merchant="Market",
			date="2026-03-01",
		)
		expenses = Expense.objects.filter(user=self.user)
		forecast = forecast_month_end(expenses, 2026, 3)
		self.assertIn("projected_total", forecast)
		self.assertGreaterEqual(forecast["projected_total"], 0)

	def test_import_budgetwise_dataset_creates_transactions(self):
		csv_content = "transaction_id,user_id,date,transaction_type,category,amount,payment_mode,location,notes\n"
		csv_content += "T1,U001,2023-01-10,Income,Salary,2000,Bank,Toronto,Monthly salary\n"
		csv_content += "T2,U001,01/15/2023,Expense,Fod,120,Card,Toronto,Grocery store\n"

		with tempfile.TemporaryDirectory() as tmpdir:
			csv_path = Path(tmpdir) / "sample.csv"
			csv_path.write_text(csv_content, encoding="utf-8")

			result = import_budgetwise_dataset(self.user, csv_path)

		self.assertIsNone(result["error"])
		self.assertEqual(result["created_income"], 1)
		self.assertEqual(result["created_expense"], 1)
		self.assertEqual(Income.objects.filter(user=self.user).count(), 1)
		self.assertEqual(Expense.objects.filter(user=self.user).count(), 1)
