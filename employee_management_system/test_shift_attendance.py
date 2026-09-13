# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
TEST SUITE: SHIFT-BASED AUTOMATIC ATTENDANCE
=============================================
Tests all core calculation requirements:
1. Normal Shifts & Overnight/Night Shifts (22:00 -> 06:00 next day)
2. Sequential pairing of multiple IN/OUT checkins (09:05 IN, 13:00 OUT, 14:00 IN, 18:10 OUT -> 8.08 hrs)
3. Late Entry and Early Exit grace periods
4. Status resolution rules (Present, Half Day, Absent, On Leave)
5. Duplicate prevention and in-place updates in MariaDB
6. End-to-end processing pipeline
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
from frappe.utils import get_datetime, getdate

if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.shift_attendance import (
	_parse_time,
	get_shift_window,
	get_active_shift_assignments,
	get_checkin_logs_for_window,
	calculate_working_hours_from_checkins,
	evaluate_grace_periods,
	determine_attendance_status,
	upsert_attendance_record,
	process_attendance_for_employee_shift,
	process_auto_attendance_for_date,
)


class TestShiftAttendance(unittest.TestCase):

	def setUp(self):
		self.test_date = getdate("2026-09-10")
		self.emp_id = "EMP-001"
		# Ensure test employee exists
		if not frappe.db.exists("Employee", self.emp_id):
			emp = frappe.get_doc({
				"doctype": "Employee",
				"naming_series": self.emp_id,
				"full_name": "Sarah Jenkins",
				"email": "sarah.jenkins@ems.com",
				"status": "Active",
			})
			emp.insert(ignore_permissions=True)
			frappe.db.commit()

	def test_01_parse_time_formats(self):
		"""Verify _parse_time correctly parses strings, timedeltas, and time objects."""
		# String
		t1 = _parse_time("09:30:00")
		self.assertEqual(t1, datetime.time(9, 30, 0))

		# Timedelta
		td = datetime.timedelta(hours=22, minutes=15)
		t2 = _parse_time(td)
		self.assertEqual(t2, datetime.time(22, 15, 0))

		# Native time
		t3 = _parse_time(datetime.time(17, 0, 0))
		self.assertEqual(t3, datetime.time(17, 0, 0))

	def test_02_normal_shift_window(self):
		"""Verify normal day shift window (09:00 - 17:00)."""
		mock_shift = {
			"start_time": "09:00:00",
			"end_time": "17:00:00",
			"begin_check_in_before_shift_start_time": 60,
			"allow_check_out_after_shift_end_time": 60,
		}
		s_start, s_end, w_start, w_end, is_overnight = get_shift_window(mock_shift, self.test_date)

		self.assertFalse(is_overnight)
		self.assertEqual(s_start, datetime.datetime(2026, 9, 10, 9, 0, 0))
		self.assertEqual(s_end, datetime.datetime(2026, 9, 10, 17, 0, 0))
		self.assertEqual(w_start, datetime.datetime(2026, 9, 10, 8, 0, 0))
		self.assertEqual(w_end, datetime.datetime(2026, 9, 10, 18, 0, 0))

	def test_03_overnight_shift_window(self):
		"""Verify overnight night shift window (22:00 - 06:00 next day)."""
		mock_shift = {
			"start_time": "22:00:00",
			"end_time": "06:00:00",
			"begin_check_in_before_shift_start_time": 60,
			"allow_check_out_after_shift_end_time": 60,
		}
		s_start, s_end, w_start, w_end, is_overnight = get_shift_window(mock_shift, self.test_date)

		self.assertTrue(is_overnight)
		self.assertEqual(s_start, datetime.datetime(2026, 9, 10, 22, 0, 0))
		# Next calendar day
		self.assertEqual(s_end, datetime.datetime(2026, 9, 11, 6, 0, 0))
		self.assertEqual(w_start, datetime.datetime(2026, 9, 10, 21, 0, 0))
		self.assertEqual(w_end, datetime.datetime(2026, 9, 11, 7, 0, 0))

	def test_04_multiple_in_out_pairs_calculation(self):
		"""
		Verify working hours calculation from multiple IN/OUT pairs:
		09:05 IN
		13:00 OUT (3h 55m = 3.9167 hrs)
		14:00 IN
		18:10 OUT (4h 10m = 4.1667 hrs)
		Total = 8.08 hrs
		"""
		logs = [
			{"name": "LOG-1", "time": "2026-09-10 09:05:00", "log_type": "IN"},
			{"name": "LOG-2", "time": "2026-09-10 13:00:00", "log_type": "OUT"},
			{"name": "LOG-3", "time": "2026-09-10 14:00:00", "log_type": "IN"},
			{"name": "LOG-4", "time": "2026-09-10 18:10:00", "log_type": "OUT"},
		]
		res = calculate_working_hours_from_checkins(logs)

		self.assertEqual(res["total_working_hours"], 8.08)
		self.assertTrue(res["has_valid_checkin"])
		self.assertEqual(res["first_in"], datetime.datetime(2026, 9, 10, 9, 5, 0))
		self.assertEqual(res["last_out"], datetime.datetime(2026, 9, 10, 18, 10, 0))
		self.assertEqual(len(res["intervals"]), 2)

	def test_05_consecutive_in_logs(self):
		"""Verify that consecutive INs retain earliest arrival timestamp."""
		logs = [
			{"name": "LOG-1", "time": "2026-09-10 08:58:00", "log_type": "IN"},
			{"name": "LOG-2", "time": "2026-09-10 09:05:00", "log_type": "IN"},
			{"name": "LOG-3", "time": "2026-09-10 17:00:00", "log_type": "OUT"},
		]
		res = calculate_working_hours_from_checkins(logs)
		# 08:58 to 17:00 = 8 hours 2 minutes = 8.03 hours
		self.assertAlmostEqual(res["total_working_hours"], 8.03, places=2)
		self.assertEqual(res["first_in"], datetime.datetime(2026, 9, 10, 8, 58, 0))

	def test_06_orphan_out_handling(self):
		"""Verify that an orphan OUT without prior IN is skipped gracefully."""
		logs = [
			{"name": "LOG-0", "time": "2026-09-10 07:30:00", "log_type": "OUT"},
			{"name": "LOG-1", "time": "2026-09-10 09:00:00", "log_type": "IN"},
			{"name": "LOG-2", "time": "2026-09-10 17:00:00", "log_type": "OUT"},
		]
		res = calculate_working_hours_from_checkins(logs)
		# 09:00 to 17:00 = 8.00 hours
		self.assertEqual(res["total_working_hours"], 8.00)

	def test_07_late_entry_grace_period(self):
		"""Verify late entry threshold evaluation against 15 minute grace period."""
		mock_shift = {"late_entry_grace_period": 15, "early_exit_grace_period": 15}
		shift_start = datetime.datetime(2026, 9, 10, 9, 0, 0)
		shift_end = datetime.datetime(2026, 9, 10, 17, 0, 0)

		# On time (within 15 min grace: 09:10 <= 09:15)
		late_entry, early_exit = evaluate_grace_periods(
			mock_shift,
			shift_start,
			shift_end,
			first_in=datetime.datetime(2026, 9, 10, 9, 10, 0),
			last_out=datetime.datetime(2026, 9, 10, 17, 5, 0),
		)
		self.assertEqual(late_entry, 0)
		self.assertEqual(early_exit, 0)

		# Late entry (09:20 > 09:15)
		late_entry, early_exit = evaluate_grace_periods(
			mock_shift,
			shift_start,
			shift_end,
			first_in=datetime.datetime(2026, 9, 10, 9, 20, 0),
			last_out=datetime.datetime(2026, 9, 10, 17, 5, 0),
		)
		self.assertEqual(late_entry, 1)
		self.assertEqual(early_exit, 0)

	def test_08_early_exit_grace_period(self):
		"""Verify early exit threshold evaluation against 15 minute grace period."""
		mock_shift = {"late_entry_grace_period": 15, "early_exit_grace_period": 15}
		shift_start = datetime.datetime(2026, 9, 10, 9, 0, 0)
		shift_end = datetime.datetime(2026, 9, 10, 17, 0, 0)

		# On time checkout (16:50 >= 16:45)
		late_entry, early_exit = evaluate_grace_periods(
			mock_shift,
			shift_start,
			shift_end,
			first_in=datetime.datetime(2026, 9, 10, 8, 55, 0),
			last_out=datetime.datetime(2026, 9, 10, 16, 50, 0),
		)
		self.assertEqual(early_exit, 0)

		# Early exit (16:30 < 16:45)
		late_entry, early_exit = evaluate_grace_periods(
			mock_shift,
			shift_start,
			shift_end,
			first_in=datetime.datetime(2026, 9, 10, 8, 55, 0),
			last_out=datetime.datetime(2026, 9, 10, 16, 30, 0),
		)
		self.assertEqual(early_exit, 1)

	def test_09_status_resolution_rules(self):
		"""Verify status determination: Present, Half Day, Absent, On Leave."""
		mock_shift = {
			"working_hours_threshold_for_half_day": 4.0,
			"working_hours_threshold_for_present": 8.0,
			"working_hours_threshold_for_absent": 1.0,
		}

		# 1. No valid check-in -> Absent
		s1 = determine_attendance_status(mock_shift, working_hours=0.0, has_valid_checkin=False, is_on_leave=False)
		self.assertEqual(s1, "Absent")

		# 2. Hours below half-day threshold (e.g. 2.5 hrs) -> Absent
		s2 = determine_attendance_status(mock_shift, working_hours=2.5, has_valid_checkin=True, is_on_leave=False)
		self.assertEqual(s2, "Absent")

		# 3. Hours between 4.0 and 8.0 (e.g. 5.5 hrs) -> Half Day
		s3 = determine_attendance_status(mock_shift, working_hours=5.5, has_valid_checkin=True, is_on_leave=False)
		self.assertEqual(s3, "Half Day")

		# 4. Hours meeting full-day threshold (e.g. 8.0 hrs) -> Present
		s4 = determine_attendance_status(mock_shift, working_hours=8.0, has_valid_checkin=True, is_on_leave=False)
		self.assertEqual(s4, "Present")

		# 5. Approved Leave with 0 worked hours -> On Leave
		s5 = determine_attendance_status(mock_shift, working_hours=0.0, has_valid_checkin=False, is_on_leave=True)
		self.assertEqual(s5, "On Leave")

		# 6. Approved Leave but worked full day (>= 8.0 hrs) -> Present
		s6 = determine_attendance_status(mock_shift, working_hours=8.2, has_valid_checkin=True, is_on_leave=True)
		self.assertEqual(s6, "Present")

	def test_10_duplicate_prevention_upsert(self):
		"""Verify that recalculation updates the existing record in-place without duplicating."""
		date_str = "2026-09-12"
		# Clean previous test record if any
		frappe.db.sql(f"DELETE FROM `tabAttendance` WHERE employee = '{self.emp_id}' AND attendance_date = '{date_str}'")
		frappe.db.commit()

		# Run 1: Insert Initial
		r1 = upsert_attendance_record(
			employee=self.emp_id,
			attendance_date=date_str,
			status="Half Day",
			shift="Day Shift",
			working_hours=4.5,
		)
		self.assertEqual(r1["action"], "created")
		att_id = r1["attendance_id"]

		# Verify 1 record in DB
		count1 = frappe.db.count("Attendance", {"employee": self.emp_id, "attendance_date": date_str})
		self.assertEqual(count1, 1)

		# Run 2: Recalculate (e.g. late checkout logged)
		r2 = upsert_attendance_record(
			employee=self.emp_id,
			attendance_date=date_str,
			status="Present",
			shift="Day Shift",
			working_hours=8.1,
		)
		self.assertEqual(r2["action"], "updated")
		self.assertEqual(r2["attendance_id"], att_id)

		# Verify STILL exactly 1 record in DB
		count2 = frappe.db.count("Attendance", {"employee": self.emp_id, "attendance_date": date_str})
		self.assertEqual(count2, 1)

		# Verify updated values in DB
		doc = frappe.get_doc("Attendance", att_id)
		self.assertEqual(doc.status, "Present")
		self.assertEqual(doc.working_hours, 8.1)

		# Cleanup
		frappe.db.sql(f"DELETE FROM `tabAttendance` WHERE name = '{att_id}'")
		frappe.db.commit()

	def test_11_end_to_end_overnight_shift(self):
		"""
		End-to-end integration test for Night Shift:
		Shift: 22:00 to 06:00 next day
		Logs:
		2026-09-15 22:05:00 IN
		2026-09-16 06:02:00 OUT
		Duration = 7 hours 57 mins = ~7.95 hours (rounded to 8.0 for half day threshold)
		"""
		# Ensure Night Shift exists
		if not frappe.db.exists("Shift Type", "Night Shift"):
			st = frappe.get_doc({
				"doctype": "Shift Type",
				"shift_name": "Night Shift",
				"start_time": "22:00:00",
				"end_time": "06:00:00",
				"enable_auto_attendance": 1,
				"late_entry_grace_period": 15,
				"early_exit_grace_period": 15,
				"working_hours_threshold_for_half_day": 4.0,
				"working_hours_threshold_for_present": 7.5,
			})
			st.insert(ignore_permissions=True)
			frappe.db.commit()

		att_date = "2026-09-15"
		# Clean previous checkins and attendance
		frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{self.emp_id}'")
		frappe.db.sql(f"DELETE FROM `tabAttendance` WHERE employee = '{self.emp_id}' AND attendance_date = '{att_date}'")
		frappe.db.commit()

		# Insert checkins spanning midnight
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": self.emp_id,
			"time": "2026-09-15 21:58:00",
			"log_type": "IN",
		}).insert(ignore_permissions=True)

		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": self.emp_id,
			"time": "2026-09-16 06:02:00",
			"log_type": "OUT",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Run processing
		res = process_attendance_for_employee_shift(
			employee=self.emp_id,
			shift_type_name="Night Shift",
			attendance_date=att_date,
		)

		self.assertEqual(res["status"], "Present")
		self.assertEqual(res["shift"], "Night Shift")
		self.assertAlmostEqual(res["working_hours"], 8.07, places=1)
		self.assertEqual(res["late_entry"], 0)
		self.assertEqual(res["early_exit"], 0)

		# Verify MariaDB persisted doc
		doc = frappe.get_doc("Attendance", res["attendance_id"])
		self.assertEqual(doc.status, "Present")
		self.assertIn("Overnight", doc.remarks)

		# Cleanup
		frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{self.emp_id}'")
		frappe.db.sql(f"DELETE FROM `tabAttendance` WHERE name = '{res['attendance_id']}'")
		frappe.db.commit()

	def test_12_api_employee_checkin_and_checkout(self):
		"""Verify employee_checkin and employee_checkout API endpoints."""
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import (
			employee_checkin,
			employee_checkout,
		)

		c_in = employee_checkin(employee=self.emp_id, log_type="IN")
		self.assertEqual(c_in["employee"], self.emp_id)
		self.assertEqual(c_in["log_type"], "IN")

		c_out = employee_checkout(employee=self.emp_id)
		self.assertEqual(c_out["employee"], self.emp_id)
		self.assertEqual(c_out["log_type"], "OUT")

		# Cleanup
		frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{self.emp_id}'")
		frappe.db.commit()

	def test_13_api_recalculate_attendance(self):
		"""Verify recalculate_attendance API endpoint."""
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import recalculate_attendance

		# Ensure a Shift Assignment exists
		if not frappe.db.exists("Shift Assignment", {"employee": self.emp_id, "shift_type": "Day Shift"}):
			frappe.get_doc({
				"doctype": "Shift Assignment",
				"employee": self.emp_id,
				"shift_type": "Day Shift",
				"start_date": "2026-09-01",
				"status": "Active",
			}).insert(ignore_permissions=True)
			frappe.db.commit()

		res = recalculate_attendance(attendance_date="2026-09-10", shift_type="Day Shift")
		self.assertIn("Successfully processed attendance", res["message"])
		self.assertGreaterEqual(res["count"], 1)

	def test_14_api_get_attendance_formatted(self):
		"""Verify get_attendance returns formatted check_in and check_out strings for UI."""
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import get_attendance

		records = get_attendance(employee=self.emp_id)
		self.assertIsInstance(records, list)
		if records:
			r = records[0]
			self.assertIn("check_in", r)
			self.assertIn("check_out", r)
			self.assertIn("working_hours", r)


if __name__ == "__main__":
	unittest.main()

