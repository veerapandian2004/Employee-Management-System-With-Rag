# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
Unit & Integration Test Suite for EMS AI Assistant Result Formatter
===================================================================
Validates:
- Strict adherence to the 9 rules and prompt contract
- Empty result handling returning standard message
- Humanization and formatting of scalar counts, totals, and averages
- Leave requests, attendance records, and salary slip humanization
- Plain text generation without SQL blocks or invented data
- Whitelisted API endpoints and pipeline integration
"""

import os
import sys
import unittest

app_root = "/home/tui013/frappe-benchv/apps/employee_management_system"
if app_root in sys.path:
	sys.path.remove(app_root)
sys.path.insert(0, app_root)
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir in sys.path:
	sys.path.remove(cur_dir)

# Ensure frappe environment is initialized when running with bench python
try:
	import frappe
	if not frappe.db:
		frappe.init(site="hospital.localhost")
		frappe.connect()
except Exception:
	pass

from employee_management_system.employee_management_system.result_formatter import (
	RESULT_FORMATTER_SYSTEM_PROMPT,
	EMPTY_RESULT_MESSAGE,
	format_database_result,
	_format_date_human,
	_format_currency,
)


class TestResultFormatter(unittest.TestCase):

	# -------------------------------------------------------------
	# 1. SYSTEM PROMPT CONTRACT & RULES
	# -------------------------------------------------------------
	def test_prompt_contract_contains_all_rules(self):
		self.assertIn("EMS AI Assistant Result Formatter", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("1. Use only the provided database result.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("2. Never invent missing values.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("3. Never assume information not present in the result.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("4. Never reveal information that is not included in the authorized result.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("5. Keep the response concise and professional.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("6. Explain totals, counts, dates, and trends clearly.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("7. If no records are returned, clearly say that no matching records were found.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("8. Do not generate new SQL.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("9. Do not claim that additional database access occurred.", RESULT_FORMATTER_SYSTEM_PROMPT)
		self.assertIn("Return the final user-facing answer as plain text.", RESULT_FORMATTER_SYSTEM_PROMPT)

	# -------------------------------------------------------------
	# 2. EMPTY RESULT HANDLING (Rule 7)
	# -------------------------------------------------------------
	def test_empty_results_return_standard_message(self):
		self.assertEqual(EMPTY_RESULT_MESSAGE, "I couldn't find any matching records for your request.")
		self.assertEqual(
			format_database_result("How many employees are in Sales?", []),
			EMPTY_RESULT_MESSAGE,
		)
		self.assertEqual(
			format_database_result("Show pending leave requests", None),
			EMPTY_RESULT_MESSAGE,
		)
		self.assertEqual(
			format_database_result("Who is absent today?", []),
			EMPTY_RESULT_MESSAGE,
		)

	# -------------------------------------------------------------
	# 3. COUNT / AGGREGATION EXPLANATIONS
	# -------------------------------------------------------------
	def test_employee_count_in_department_example(self):
		# Exact example from specification
		user_q = "How many employees are in Engineering?"
		db_res = [{"employee_count": 25}]
		expected = "There are currently 25 employees in the Engineering department."
		res = format_database_result(user_q, db_res)
		self.assertEqual(res, expected)

	def test_general_employee_count(self):
		user_q = "How many active employees are there?"
		db_res = [{"employee_count": 42}]
		res = format_database_result(user_q, db_res)
		self.assertEqual(res, "There are currently 42 matching employees.")

	def test_total_currency_aggregation(self):
		user_q = "What is the total salary disbursement for August?"
		db_res = [{"total_amount": 125000}]
		res = format_database_result(user_q, db_res)
		self.assertEqual(res, "The total amount is $125,000.")

	def test_total_days_aggregation(self):
		user_q = "What is the total leave days taken?"
		db_res = [{"total_days": 14}]
		res = format_database_result(user_q, db_res)
		self.assertEqual(res, "The total is 14 days.")

	# -------------------------------------------------------------
	# 4. LEAVE REQUEST EXPLANATIONS
	# -------------------------------------------------------------
	def test_single_pending_leave_request_example(self):
		# Exact example from specification
		user_q = "Show pending leave requests."
		db_res = [
			{
				"employee_name": "John Doe",
				"leave_type": "Sick Leave",
				"from_date": "2026-09-10",
				"to_date": "2026-09-12",
			}
		]
		expected = (
			"There is 1 pending leave request:\n\n"
			"* John Doe — Sick Leave\n"
			"* September 10, 2026 to September 12, 2026"
		)
		res = format_database_result(user_q, db_res)
		self.assertEqual(res, expected)

	def test_multiple_pending_leave_requests(self):
		user_q = "Show pending leave requests."
		db_res = [
			{
				"employee_name": "Alice Smith",
				"leave_type": "Casual Leave",
				"from_date": "2026-09-15",
				"to_date": "2026-09-15",
			},
			{
				"employee_name": "Bob Jones",
				"leave_type": "Annual Leave",
				"from_date": "2026-09-20",
				"to_date": "2026-09-25",
			},
		]
		res = format_database_result(user_q, db_res)
		self.assertIn("There are 2 pending leave requests:", res)
		self.assertIn("Alice Smith — Casual Leave", res)
		self.assertIn("September 15, 2026", res)
		self.assertIn("Bob Jones — Annual Leave", res)
		self.assertIn("September 20, 2026 to September 25, 2026", res)

	# -------------------------------------------------------------
	# 5. ATTENDANCE EXPLANATIONS
	# -------------------------------------------------------------
	def test_attendance_records_explanation(self):
		user_q = "Who is absent today?"
		db_res = [
			{
				"employee_name": "Charlie Brown",
				"status": "Absent",
				"attendance_date": "2026-09-08",
			}
		]
		res = format_database_result(user_q, db_res)
		self.assertIn("There is 1 attendance record:", res)
		self.assertIn("Charlie Brown: Absent on September 8, 2026", res)

	# -------------------------------------------------------------
	# 6. SALARY SLIP EXPLANATIONS
	# -------------------------------------------------------------
	def test_salary_slips_explanation(self):
		user_q = "Show my salary slips."
		db_res = [
			{
				"employee": "EMP-0001",
				"salary_month": "August 2026",
				"gross_pay": 5000,
				"net_pay": 4500,
				"status": "Submitted",
			}
		]
		res = format_database_result(user_q, db_res)
		self.assertIn("Found 1 salary slip:", res)
		self.assertIn("EMP-0001", res)
		self.assertIn("August 2026", res)
		self.assertIn("Gross: $5,000", res)
		self.assertIn("Net: $4,500", res)
		self.assertIn("[Submitted]", res)

	# -------------------------------------------------------------
	# 7. LLM RESPONSE PASSTHROUGH
	# -------------------------------------------------------------
	def test_external_llm_response_passthrough(self):
		llm_text = '"There are currently 5 employees on leave today."'
		res = format_database_result(
			user_question="Who is on leave?",
			database_result=[{"employee_count": 5}],
			llm_response=llm_text,
		)
		self.assertEqual(res, "There are currently 5 employees on leave today.")

	# -------------------------------------------------------------
	# 8. FRAPPE WHITELISTED API INTEGRATION
	# -------------------------------------------------------------
	def test_api_get_result_formatter_prompt(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import get_result_formatter_prompt
		res = get_result_formatter_prompt()
		self.assertIn("system_prompt", res)
		self.assertIn("EMS AI Assistant Result Formatter", res["system_prompt"])

	def test_api_format_database_result_endpoint(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import format_database_result_api
		res = format_database_result_api(
			user_question="How many employees are in Engineering?",
			database_result=[{"employee_count": 25}],
		)
		self.assertIn("explanation", res)
		self.assertEqual(res["explanation"], "There are currently 25 employees in the Engineering department.")

	def test_api_format_database_result_endpoint_json_string(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import format_database_result_api
		res = format_database_result_api(
			user_question="Show pending leave requests.",
			database_result='[{"employee_name": "John Doe", "leave_type": "Sick Leave", "from_date": "2026-09-10", "to_date": "2026-09-12"}]',
		)
		self.assertIn("explanation", res)
		self.assertIn("John Doe — Sick Leave", res["explanation"])


if __name__ == "__main__":
	runner = unittest.TextTestRunner(verbosity=2)
	suite = unittest.TestLoader().loadTestsFromTestCase(TestResultFormatter)
	test_result = runner.run(suite)
	sys.exit(0 if test_result.wasSuccessful() else 1)
