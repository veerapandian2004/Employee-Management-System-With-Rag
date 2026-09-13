# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
TEST SUITE: SHIFT ATTENDANCE ENHANCEMENTS
=========================================
Tests weekly off and holiday validation, status priorities:
Holiday > Weekly Off > On Leave > Present > Half Day > Absent,
idempotent upsert, and prevention of overwriting higher priority statuses.
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
from frappe.utils import getdate

if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.shift_attendance import (
	is_company_holiday,
	is_weekly_off_for_shift,
	determine_attendance_status,
	upsert_attendance_record,
	STATUS_PRIORITY,
)


class TestShiftAttendanceEnhancements(unittest.TestCase):

	def setUp(self):
		try:
			frappe.db.sql("SELECT 1")
		except Exception:
			frappe.connect()

		self.emp_id = frappe.db.get_value("Employee", {"status": "Active"}, "name") or "EMP-001"

		self.shift_id = "TEST-SHIFT-ENH"
		if not frappe.db.exists("Shift Type", self.shift_id):
			frappe.get_doc({
				"doctype": "Shift Type",
				"name": self.shift_id,
				"shift_name": self.shift_id,
				"start_time": "09:00:00",
				"end_time": "18:00:00",
				"weekly_off_days": "Sunday",
				"working_hours_threshold_for_half_day": 4.0,
				"working_hours_threshold_for_present": 8.0,
			}).insert(ignore_permissions=True)
			frappe.db.commit()

	def tearDown(self):
		try:
			frappe.db.rollback()
		except Exception:
			pass

	def test_is_company_holiday(self):
		test_holiday_date = "2026-10-02"
		# Cleanup if exists
		frappe.db.delete("Holiday", {"holiday_date": test_holiday_date})

		frappe.get_doc({
			"doctype": "Holiday",
			"holiday_name": "Gandhi Jayanti",
			"holiday_date": test_holiday_date,
			"description": "National Holiday",
		}).insert(ignore_permissions=True)

		is_hol, hol_name = is_company_holiday(test_holiday_date)
		self.assertTrue(is_hol)
		self.assertEqual(hol_name, "Gandhi Jayanti")

		# Non-holiday
		is_hol_no, _ = is_company_holiday("2026-10-03")
		self.assertFalse(is_hol_no)

	def test_is_weekly_off_for_shift(self):
		# Shift configured with weekly_off_days = "Sunday"
		sunday_date = "2026-09-13"  # Sunday
		monday_date = "2026-09-14"  # Monday
		self.assertTrue(is_weekly_off_for_shift(self.shift_id, sunday_date))
		self.assertFalse(is_weekly_off_for_shift(self.shift_id, monday_date))

		# Fallback to Saturday, Sunday if empty
		if frappe.db.exists("Shift Type", "TEST-SHIFT-DEF"):
			frappe.db.delete("Shift Type", "TEST-SHIFT-DEF")

		shift_default = frappe.get_doc({
			"doctype": "Shift Type",
			"name": "TEST-SHIFT-DEF",
			"shift_name": "TEST-SHIFT-DEF",
			"start_time": "09:00:00",
			"end_time": "18:00:00",
			"weekly_off_days": "",
		}).insert(ignore_permissions=True)
		saturday_date = "2026-09-12"  # Saturday
		self.assertTrue(is_weekly_off_for_shift(shift_default, saturday_date))
		self.assertTrue(is_weekly_off_for_shift(shift_default, sunday_date))
		self.assertFalse(is_weekly_off_for_shift(shift_default, monday_date))

	def test_determine_attendance_status_priority(self):
		shift_doc = frappe.get_doc("Shift Type", self.shift_id)

		# 1. Holiday takes highest priority
		status = determine_attendance_status(
			shift_doc,
			working_hours=0.0,
			has_valid_checkin=False,
			is_holiday=True,
			is_weekly_off=True,
			is_on_leave=True,
		)
		self.assertEqual(status, "Holiday")

		# 2. Weekly Off takes priority over Leave & Absent
		status = determine_attendance_status(
			shift_doc,
			working_hours=0.0,
			has_valid_checkin=False,
			is_holiday=False,
			is_weekly_off=True,
			is_on_leave=True,
		)
		self.assertEqual(status, "Weekly Off")

		# 3. Approved Leave takes priority over Absent
		status = determine_attendance_status(
			shift_doc,
			working_hours=0.0,
			has_valid_checkin=False,
			is_holiday=False,
			is_weekly_off=False,
			is_on_leave=True,
		)
		self.assertEqual(status, "On Leave")

		# 4. Normal working day with 0 checkin -> Absent
		status = determine_attendance_status(
			shift_doc,
			working_hours=0.0,
			has_valid_checkin=False,
		)
		self.assertEqual(status, "Absent")

		# 5. Half Day (4 to <8 hours)
		status = determine_attendance_status(
			shift_doc,
			working_hours=5.5,
			has_valid_checkin=True,
		)
		self.assertEqual(status, "Half Day")

		# 6. Present (>= 8 hours)
		status = determine_attendance_status(
			shift_doc,
			working_hours=8.2,
			has_valid_checkin=True,
		)
		self.assertEqual(status, "Present")

	def test_status_priority_guard_in_upsert(self):
		test_date = "2026-09-15"
		frappe.db.delete("Attendance", {"employee": self.emp_id, "attendance_date": test_date})

		# Step 1: Record marked as Holiday
		upsert_attendance_record(
			employee=self.emp_id,
			attendance_date=test_date,
			status="Holiday",
			shift=self.shift_id,
		)
		saved_status = frappe.db.get_value(
			"Attendance",
			{"employee": self.emp_id, "attendance_date": test_date},
			"status",
		)
		self.assertEqual(saved_status, "Holiday")

		# Step 2: Auto-attendance runs later with 0 checkins -> attempts to mark Absent
		upsert_attendance_record(
			employee=self.emp_id,
			attendance_date=test_date,
			status="Absent",
			shift=self.shift_id,
			force_status=False,
		)

		# Verify priority guard protected the record from being overwritten
		preserved_status = frappe.db.get_value(
			"Attendance",
			{"employee": self.emp_id, "attendance_date": test_date},
			"status",
		)
		self.assertEqual(preserved_status, "Holiday")

	def test_idempotency_upsert(self):
		test_date = "2026-09-16"
		frappe.db.delete("Attendance", {"employee": self.emp_id, "attendance_date": test_date})

		# Upsert multiple times
		for _ in range(3):
			upsert_attendance_record(
				employee=self.emp_id,
				attendance_date=test_date,
				status="Present",
				shift=self.shift_id,
				working_hours=8.0,
			)

		count = frappe.db.count("Attendance", {"employee": self.emp_id, "attendance_date": test_date})
		self.assertEqual(count, 1)


if __name__ == "__main__":
	unittest.main()
