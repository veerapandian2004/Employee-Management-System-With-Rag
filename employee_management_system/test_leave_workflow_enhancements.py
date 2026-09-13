# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
TEST SUITE: LEAVE WORKFLOW ENHANCEMENTS
=======================================
Tests real-time leave balance validation, overlap checks, immediate attendance
synchronization upon approval within transaction, leave cancellation rules,
and attendance status reversion with balance restoration.
"""

import datetime
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

import frappe
from frappe.utils import getdate, nowdate, add_days

if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.api import (
	get_leave_balance,
	create_leave_application,
	update_leave_status,
	cancel_leave_application,
)


class TestLeaveWorkflowEnhancements(unittest.TestCase):

	def setUp(self):
		try:
			frappe.db.sql("SELECT 1")
		except Exception:
			frappe.connect()

		frappe.set_user("Administrator")
		self.emp_email = "emp.leave01@hospital.localhost"

		# Ensure user exists for employee
		if not frappe.db.exists("User", self.emp_email):
			frappe.db.sql("""
				INSERT INTO `tabUser` (name, email, first_name, enabled, docstatus)
				VALUES (%s, %s, 'LeaveEmp', 1, 0)
			""", (self.emp_email, self.emp_email))
			frappe.db.sql("""
				INSERT INTO `tabHas Role` (name, parent, parenttype, parentfield, role)
				VALUES (%s, %s, 'User', 'roles', 'Employee')
			""", (frappe.generate_hash(length=10), self.emp_email))
			frappe.db.commit()

		# Ensure employee exists
		existing_emp = frappe.db.get_value("Employee", {"email": self.emp_email}, "name")
		if not existing_emp:
			emp_doc = frappe.get_doc({
				"doctype": "Employee",
				"full_name": "Leave Test Employee",
				"email": self.emp_email,
				"user_id": self.emp_email,
				"status": "Active",
				"date_of_joining": "2024-01-01",
				"basic_salary": 50000,
			}).insert(ignore_permissions=True)
			frappe.db.commit()
			self.emp_id = emp_doc.name
		else:
			self.emp_id = existing_emp

		self.leave_type_name = "Casual Leave - Test"
		if not frappe.db.exists("Leave Type", self.leave_type_name):
			frappe.get_doc({
				"doctype": "Leave Type",
				"leave_type_name": self.leave_type_name,
				"max_days_per_year": 10,
			}).insert(ignore_permissions=True)
			frappe.db.commit()
		else:
			frappe.db.set_value("Leave Type", self.leave_type_name, "max_days_per_year", 10)
			frappe.db.commit()

		# Cleanup existing records for clean test run
		frappe.db.delete("Leave Application", {"employee": self.emp_id})
		frappe.db.delete("Attendance", {"employee": self.emp_id})
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")
		try:
			frappe.db.rollback()
		except Exception:
			try:
				frappe.connect()
			except Exception:
				pass

	def test_01_leave_balance_calculation(self):
		bal = get_leave_balance(self.emp_id, self.leave_type_name)
		self.assertEqual(bal["max_days_per_year"], 10)
		self.assertEqual(bal["consumed"], 0)
		self.assertEqual(bal["remaining_balance"], 10)
		self.assertEqual(bal["available_balance"], 10)

	def test_02_balance_deficit_validation(self):
		# Attempt to apply for 15 days (allocated: 10)
		with self.assertRaises(Exception) as ctx:
			create_leave_application({
				"employee": self.emp_id,
				"leave_type": self.leave_type_name,
				"from_date": "2026-12-01",
				"to_date": "2026-12-15",
				"reason": "Long vacation exceeding quota",
			})
		self.assertIn("cannot apply", str(ctx.exception).lower())

	def test_03_overlap_prevention(self):
		# Apply for 2026-11-01 to 2026-11-03 (3 days)
		app1 = create_leave_application({
			"employee": self.emp_id,
			"leave_type": self.leave_type_name,
			"from_date": "2026-11-01",
			"to_date": "2026-11-03",
			"reason": "First leave request",
		})
		self.assertTrue(bool(app1.get("name")))

		# Attempt overlapping leave (2026-11-02 to 2026-11-04)
		with self.assertRaises(Exception) as ctx:
			create_leave_application({
				"employee": self.emp_id,
				"leave_type": self.leave_type_name,
				"from_date": "2026-11-02",
				"to_date": "2026-11-04",
				"reason": "Conflicting leave request",
			})
		self.assertIn("already exists", str(ctx.exception).lower())

	def test_04_approval_attendance_sync(self):
		# Create application
		app = create_leave_application({
			"employee": self.emp_id,
			"leave_type": self.leave_type_name,
			"from_date": "2026-11-10",
			"to_date": "2026-11-12",
			"reason": "Conference attendance",
		})
		app_name = app.get("name")

		# Approve application
		update_leave_status(app_name, "Approved")

		# Verify attendance sync for all 3 days
		for dt in ["2026-11-10", "2026-11-11", "2026-11-12"]:
			att = frappe.db.get_value(
				"Attendance",
				{"employee": self.emp_id, "attendance_date": dt},
				["status", "leave_application", "leave_type"],
				as_dict=True,
			)
			self.assertIsNotNone(att, f"Attendance record missing for {dt}")
			self.assertEqual(att.status, "On Leave")
			self.assertEqual(att.leave_application, app_name)

	def test_05_cancellation_and_attendance_reversion(self):
		# Create and approve application
		app = create_leave_application({
			"employee": self.emp_id,
			"leave_type": self.leave_type_name,
			"from_date": "2026-11-20",
			"to_date": "2026-11-22",
			"reason": "Medical checkup",
		})
		app_name = app.get("name")
		update_leave_status(app_name, "Approved")

		# Check balance before cancel: consumed=3, remaining=7
		bal = get_leave_balance(self.emp_id, self.leave_type_name)
		self.assertEqual(bal["consumed"], 3)
		self.assertEqual(bal["available_balance"], 7)

		# Cancel the application
		res = cancel_leave_application(app_name, reason="Checkup rescheduled")
		self.assertEqual(res["status"], "Cancelled")
		self.assertEqual(res["cancellation_reason"], "Checkup rescheduled")

		# Check balance restored: consumed=0, remaining=10
		bal_restored = get_leave_balance(self.emp_id, self.leave_type_name)
		self.assertEqual(bal_restored["consumed"], 0)
		self.assertEqual(bal_restored["available_balance"], 10)

		# Check attendance records are no longer "On Leave" with this leave application
		for dt in ["2026-11-20", "2026-11-21", "2026-11-22"]:
			att_status = frappe.db.get_value(
				"Attendance",
				{"employee": self.emp_id, "attendance_date": dt},
				"status",
			)
			self.assertNotEqual(att_status, "On Leave")

	def test_06_employee_cannot_cancel_past_approved_leave(self):
		# Past leave application
		past_from = "2026-08-01"
		past_to = "2026-08-02"
		app = create_leave_application({
			"employee": self.emp_id,
			"leave_type": self.leave_type_name,
			"from_date": past_from,
			"to_date": past_to,
			"reason": "Past emergency",
		})
		app_name = app.get("name")
		update_leave_status(app_name, "Approved")

		# Switch to employee user
		frappe.set_user(self.emp_email)
		with self.assertRaises(Exception) as ctx:
			cancel_leave_application(app_name, reason="Attempt to cancel past leave")
		self.assertIn("cannot cancel approved leave that has already commenced", str(ctx.exception).lower())

		# Administrator can cancel it
		frappe.set_user("Administrator")
		res = cancel_leave_application(app_name, reason="Admin override cancellation")
		self.assertEqual(res["status"], "Cancelled")


if __name__ == "__main__":
	unittest.main()
