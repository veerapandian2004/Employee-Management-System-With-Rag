# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
TEST SUITE: PAYROLL & LOP ENHANCEMENTS
======================================
Tests dynamic Loss of Pay (LOP) calculation from tabAttendance,
pro-rated daily salary and LOP deduction, idempotent batch payroll generation,
salary slip PDF generation & download, and individual/batch email dispatch tracking.
"""

import calendar
import datetime
import os
import sys
import unittest
from unittest.mock import patch

app_root = "/home/tui013/frappe-benchv/apps/employee_management_system"
if app_root in sys.path:
	sys.path.remove(app_root)
sys.path.insert(0, app_root)
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir in sys.path:
	sys.path.remove(cur_dir)

import frappe
from frappe.utils import flt, getdate

if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.api import (
	calculate_lop_for_employee_month,
	create_salary_slip,
	generate_batch_payroll,
	download_salary_slip_pdf,
	send_salary_slip_email,
	send_batch_salary_slip_emails,
)


class TestPayrollEnhancements(unittest.TestCase):

	def setUp(self):
		frappe.set_user("Administrator")
		self.salary_month = "2026-09"

		# Pick or create a test employee with basic salary 60,000
		existing = frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "department", "email"], limit=1)
		if existing:
			self.emp_id = existing[0].name
			self.department = existing[0].department or "Engineering"
			frappe.db.set_value("Employee", self.emp_id, "basic_salary", 60000.0)
			frappe.db.set_value("Employee", self.emp_id, "department", self.department)
			if not existing[0].email:
				frappe.db.set_value("Employee", self.emp_id, "email", "test.employee@hospital.localhost")
			frappe.db.commit()
		else:
			self.emp_id = "EMP-001"
			self.department = "Engineering"

		# Ensure unpaid leave type exists
		if not frappe.db.exists("Leave Type", "Leave Without Pay"):
			frappe.get_doc({
				"doctype": "Leave Type",
				"leave_type_name": "Leave Without Pay",
				"max_days_per_year": 0,
			}).insert(ignore_permissions=True)
			frappe.db.commit()

		# Cleanup existing salary slips and test attendance for this employee in 2026-09
		frappe.db.delete("Salary Slip", {"employee": self.emp_id, "salary_month": self.salary_month})
		frappe.db.delete("Attendance", {
			"employee": self.emp_id,
			"attendance_date": ["between", ["2026-09-01", "2026-09-30"]],
		})
		frappe.db.commit()

	def tearDown(self):
		frappe.db.rollback()

	def test_01_lop_calculation_from_attendance(self):
		# Setup attendance records in September (30 days total)
		# 1. Two Absent days (2026-09-02, 2026-09-03)
		frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.emp_id,
			"attendance_date": "2026-09-02",
			"status": "Absent",
			"working_hours": 0.0,
		}).insert(ignore_permissions=True)

		frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.emp_id,
			"attendance_date": "2026-09-03",
			"status": "Absent",
			"working_hours": 0.0,
		}).insert(ignore_permissions=True)

		# 2. One Half Day (2026-09-04) -> 0.5 absent
		frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.emp_id,
			"attendance_date": "2026-09-04",
			"status": "Half Day",
			"working_hours": 4.5,
		}).insert(ignore_permissions=True)

		# 3. One Unpaid Leave day (2026-09-05) -> 1.0 unpaid leave
		frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.emp_id,
			"attendance_date": "2026-09-05",
			"status": "On Leave",
			"leave_type": "Leave Without Pay",
			"working_hours": 0.0,
		}).insert(ignore_permissions=True)

		frappe.db.commit()

		# Calculate LOP
		lop = calculate_lop_for_employee_month(self.emp_id, self.salary_month)

		self.assertEqual(lop["days_in_month"], 30)
		self.assertEqual(lop["monthly_basic"], 60000.0)
		self.assertEqual(lop["daily_salary"], 2000.0)  # 60,000 / 30 = 2000
		self.assertEqual(lop["absent_days"], 2.5)      # 2 + 0.5
		self.assertEqual(lop["unpaid_leave_days"], 1.0)
		self.assertEqual(lop["lop_days"], 3.5)
		self.assertEqual(lop["lop_deduction"], 7000.0)  # 3.5 * 2000

	def test_02_idempotent_batch_payroll(self):
		# Create an absent record
		frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.emp_id,
			"attendance_date": "2026-09-10",
			"status": "Absent",
			"working_hours": 0.0,
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# 1. Run batch payroll for employee's department
		res1 = generate_batch_payroll(
			salary_month=self.salary_month,
			employee=self.emp_id,
			department=self.department,
			regenerate=False,
		)
		self.assertTrue(res1.get("payroll_id"))
		self.assertGreaterEqual(res1.get("processed_slips"), 1)

		# Verify slip created for test employee
		slip1 = frappe.db.get_value(
			"Salary Slip",
			{"employee": self.emp_id, "salary_month": self.salary_month},
			["name", "lop_days", "lop_deduction", "email_status"],
			as_dict=True,
		)
		self.assertIsNotNone(slip1)
		self.assertGreaterEqual(flt(slip1.lop_days), 1.0)
		self.assertEqual(slip1.email_status, "Pending")

		# 2. Run batch payroll AGAIN without regenerate (Idempotency test)
		res2 = generate_batch_payroll(
			salary_month=self.salary_month,
			employee=self.emp_id,
			department=self.department,
			regenerate=False,
		)
		self.assertGreaterEqual(res2.get("skipped_slips"), 1)

		# Ensure exactly 1 Salary Slip exists for this employee and month
		count = frappe.db.count("Salary Slip", {"employee": self.emp_id, "salary_month": self.salary_month})
		self.assertEqual(count, 1)

	def test_03_salary_slip_pdf_generation(self):
		# Ensure a salary slip exists
		slip_name = frappe.db.get_value(
			"Salary Slip",
			{"employee": self.emp_id, "salary_month": self.salary_month},
			"name",
		)
		if not slip_name:
			slip = create_salary_slip({
				"employee": self.emp_id,
				"salary_month": self.salary_month,
				"basic_pay": 60000.0,
				"hra": 24000.0,
				"gross_pay": 84000.0,
				"net_pay": 84000.0,
			})
			slip_name = slip.get("name")

		download_salary_slip_pdf(slip_name)
		self.assertEqual(frappe.response.get("type"), "pdf")
		self.assertTrue(bool(frappe.response.get("filecontent")))
		self.assertIn("Salary_Slip_", frappe.response.get("filename"))

	@patch("frappe.sendmail")
	def test_04_email_status_dispatch_tracking(self, mock_sendmail):
		mock_sendmail.return_value = True

		slip_name = frappe.db.get_value(
			"Salary Slip",
			{"employee": self.emp_id, "salary_month": self.salary_month},
			"name",
		)
		if not slip_name:
			slip = create_salary_slip({
				"employee": self.emp_id,
				"salary_month": self.salary_month,
				"basic_pay": 60000.0,
				"hra": 24000.0,
				"gross_pay": 84000.0,
				"net_pay": 84000.0,
			})
			slip_name = slip.get("name")

		# Send individual email
		res = send_salary_slip_email(slip_name)
		self.assertEqual(res.get("email_status"), "Sent")
		self.assertTrue(bool(res.get("email_sent_at")))

		status_in_db = frappe.db.get_value("Salary Slip", slip_name, "email_status")
		self.assertEqual(status_in_db, "Sent")

		# Test batch email dispatch
		batch_res = send_batch_salary_slip_emails(salary_month=self.salary_month, department=self.department)
		self.assertIn("sent_count", batch_res)


if __name__ == "__main__":
	unittest.main()
