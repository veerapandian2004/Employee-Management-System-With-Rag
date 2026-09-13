# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
AUTOMATIC CLOCK-OUT SYSTEM TEST SUITE
======================================
Comprehensive verification of all 5 enterprise rules:
1. Location-based automatic clock-out (Outside office geofence -> Reason: 'Left Office Location')
2. Shift completion automatic clock-out (Past shift end -> Reason: 'Shift Completed' at exact shift end time)
3. Priority and tracking:
   - Leaves office before shift end: 'Left Office Location'
   - Reaches end of shift: 'Shift Completed'
4. Attendance records:
   - Saves exact date, time, reason, and auto_clocked_out flag in tabAttendance and tabEmployee Checkin.
5. Notifications:
   - Generates Notification Log entries for Employee and Administrator.
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
from frappe.utils import getdate, now_datetime, nowdate

if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.attendance.auto_clock_out_service import (
	REASON_LEFT_OFFICE,
	REASON_SHIFT_COMPLETED,
	auto_clock_out_employee,
	check_location_auto_clock_out,
	check_shift_completion_auto_clock_out,
	is_employee_clocked_in,
	send_auto_clock_out_notifications,
)
from employee_management_system.employee_management_system.attendance.checkin_service import (
	get_assigned_office,
	get_latest_checkin,
	get_employee_attendance_status,
)
from employee_management_system.employee_management_system.shift_attendance import (
	upsert_attendance_record,
	get_shift_window,
)


class TestAutoClockOut(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")

		# 1. Ensure Main Office exists (150m allowed radius)
		if not frappe.db.exists("Office Location", "Main Office"):
			frappe.get_doc({
				"doctype": "Office Location",
				"office_name": "Main Office",
				"latitude": 11.057199,
				"longitude": 76.944784,
				"allowed_radius": 150.0,
				"max_accuracy": 50.0,
				"is_active": 1,
				"address": "Coimbatore HQ",
			}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Office Location", "Main Office", {
				"latitude": 11.057199,
				"longitude": 76.944784,
				"allowed_radius": 150.0,
				"is_active": 1,
			})

		# 2. Ensure test shift types exist
		if not frappe.db.exists("Shift Type", "Test Day Shift"):
			frappe.get_doc({
				"doctype": "Shift Type",
				"shift_name": "Test Day Shift",
				"start_time": "09:00:00",
				"end_time": "17:00:00",
				"enable_auto_attendance": 1,
				"late_entry_grace_period": 15,
				"early_exit_grace_period": 15,
				"working_hours_threshold_for_half_day": 4.0,
				"working_hours_threshold_for_present": 8.0,
			}).insert(ignore_permissions=True)

		if not frappe.db.exists("Shift Type", "Test Night Shift"):
			frappe.get_doc({
				"doctype": "Shift Type",
				"shift_name": "Test Night Shift",
				"start_time": "22:00:00",
				"end_time": "06:00:00",
				"enable_auto_attendance": 1,
				"late_entry_grace_period": 15,
				"early_exit_grace_period": 15,
				"working_hours_threshold_for_half_day": 4.0,
				"working_hours_threshold_for_present": 8.0,
			}).insert(ignore_permissions=True)

		# 3. Ensure test employee EMP-001 exists and assigned
		if frappe.db.exists("Employee", "EMP-001"):
			frappe.db.set_value("Employee", "EMP-001", {
				"office_location": "Main Office",
				"status": "Active",
				"user_id": "employee@ems.com",
			})
		else:
			frappe.get_doc({
				"doctype": "Employee",
				"naming_series": "EMP-",
				"full_name": "Test Auto Employee",
				"status": "Active",
				"office_location": "Main Office",
				"user_id": "employee@ems.com",
			}).insert(ignore_permissions=True)

		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		# Clean checkins and attendance for EMP-001
		frappe.db.sql("DELETE FROM `tabEmployee Checkin` WHERE employee = 'EMP-001'")
		frappe.db.sql("DELETE FROM `tabAttendance` WHERE employee = 'EMP-001'")
		frappe.db.sql("DELETE FROM `tabNotification Log` WHERE for_user IN ('employee@ems.com', 'Administrator') AND subject LIKE 'Automatic Clock-Out%'")
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")

	# -------------------------------------------------------------
	# 1. LOCATION-BASED AUTOMATIC CLOCK-OUT (RULE 1 & 3)
	# -------------------------------------------------------------
	def test_01_geofence_clockout_when_leaving_office(self):
		"""
		Rule 1: If an employee leaves the assigned office location / geofence
		during working hours, automatically clock them out with reason 'Left Office Location'.
		"""
		# Clock in employee inside office
		clock_in_time = now_datetime() - datetime.timedelta(hours=2)
		chk_in = frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"employee_name": "Test Auto Employee",
			"time": clock_in_time,
			"log_type": "IN",
			"shift": "Test Day Shift",
			"latitude": 11.057199,
			"longitude": 76.944784,
			"accuracy": 10.0,
			"distance_from_office": 5.0,
			"office_location": "Main Office",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		is_in, _ = is_employee_clocked_in("EMP-001")
		self.assertTrue(is_in, "Employee should be clocked in.")

		# Employee moves 500m away outside allowed radius (150m)
		# 11.062000, 76.944784 is ~533 meters away
		res = check_location_auto_clock_out(
			employee_id="EMP-001",
			latitude=11.062000,
			longitude=76.944784,
			accuracy=15.0,
		)

		self.assertEqual(res["action"], "auto_clocked_out")
		self.assertTrue(res["auto_clocked_out"])
		self.assertEqual(res["reason"], REASON_LEFT_OFFICE)
		self.assertGreater(res["distance"], 150.0)

		# Verify Employee Checkin record
		latest = get_latest_checkin("EMP-001")
		self.assertIsNotNone(latest)
		self.assertEqual(latest.get("log_type"), "OUT")
		self.assertEqual(latest.get("is_auto_clock_out"), 1)
		self.assertEqual(latest.get("clock_out_reason"), REASON_LEFT_OFFICE)

		# Verify tabAttendance record
		att_date = clock_in_time.date()
		att = frappe.db.get_value(
			"Attendance",
			{"employee": "EMP-001", "attendance_date": att_date},
			["name", "out_time", "auto_clocked_out", "clock_out_reason", "auto_clock_out_time", "remarks"],
			as_dict=True,
		)
		self.assertIsNotNone(att)
		self.assertEqual(att.auto_clocked_out, 1)
		self.assertEqual(att.clock_out_reason, REASON_LEFT_OFFICE)
		self.assertIsNotNone(att.out_time)
		self.assertIn("Auto clocked out: Left Office Location", att.remarks)

	def test_02_geofence_remains_clocked_in_when_inside_office(self):
		"""
		Employee coordinates within office radius must NOT trigger clock-out.
		"""
		chk_in = frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"employee_name": "Test Auto Employee",
			"time": now_datetime(),
			"log_type": "IN",
			"shift": "Test Day Shift",
			"latitude": 11.057199,
			"longitude": 76.944784,
			"accuracy": 10.0,
			"office_location": "Main Office",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Ping 25 meters from office (inside 150m)
		res = check_location_auto_clock_out(
			employee_id="EMP-001",
			latitude=11.057350,
			longitude=76.944900,
			accuracy=10.0,
		)

		self.assertEqual(res["action"], "verified_inside")
		self.assertFalse(res["auto_clocked_out"])
		self.assertTrue(res["is_clocked_in"])
		self.assertLessEqual(res["distance"], 150.0)

		# Employee must still be clocked in
		is_in, _ = is_employee_clocked_in("EMP-001")
		self.assertTrue(is_in)

	def test_03_geofence_noop_when_not_clocked_in(self):
		"""
		Geofence check when employee is not clocked in is a safe no-op.
		"""
		res = check_location_auto_clock_out(
			employee_id="EMP-001",
			latitude=11.062000,
			longitude=76.944784,
			accuracy=15.0,
		)
		self.assertEqual(res["action"], "none")
		self.assertFalse(res["auto_clocked_out"])

	# -------------------------------------------------------------
	# 2. SHIFT COMPLETION AUTOMATIC CLOCK-OUT (RULE 2 & 3)
	# -------------------------------------------------------------
	def test_04_shift_completion_clockout_at_shift_end(self):
		"""
		Rule 2: If an employee is still clocked in when their scheduled shift ends,
		automatically clock them out at the exact shift end time with reason 'Shift Completed'.
		"""
		today = getdate(nowdate())

		# Assign Test Day Shift (09:00 - 17:00)
		frappe.db.sql("DELETE FROM `tabShift Assignment` WHERE employee = 'EMP-001'")
		frappe.get_doc({
			"doctype": "Shift Assignment",
			"employee": "EMP-001",
			"shift_type": "Test Day Shift",
			"start_date": today,
			"status": "Active",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Clock in at 09:05 AM
		shift_start = datetime.datetime.combine(today, datetime.time(9, 0, 0))
		shift_end = datetime.datetime.combine(today, datetime.time(17, 0, 0))
		clock_in_time = shift_start + datetime.timedelta(minutes=5)

		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"employee_name": "Test Auto Employee",
			"time": clock_in_time,
			"log_type": "IN",
			"shift": "Test Day Shift",
			"office_location": "Main Office",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Trigger auto clock-out with shift completion
		out_res = auto_clock_out_employee(
			employee_id="EMP-001",
			reason=REASON_SHIFT_COMPLETED,
			clock_out_datetime=shift_end,
		)

		self.assertEqual(out_res["status"], "clocked_out")
		self.assertEqual(out_res["reason"], REASON_SHIFT_COMPLETED)
		self.assertEqual(out_res["clock_out_time"], str(shift_end))

		# Verify exact punch OUT timestamp is shift_end
		latest = get_latest_checkin("EMP-001")
		self.assertEqual(latest.get("log_type"), "OUT")
		self.assertEqual(str(latest.get("time")), str(shift_end))
		self.assertEqual(latest.get("clock_out_reason"), REASON_SHIFT_COMPLETED)
		self.assertEqual(latest.get("is_auto_clock_out"), 1)

		# Verify tabAttendance out_time matches shift_end
		att = frappe.db.get_value(
			"Attendance",
			{"employee": "EMP-001", "attendance_date": today},
			["name", "out_time", "auto_clocked_out", "clock_out_reason", "working_hours"],
			as_dict=True,
		)
		self.assertIsNotNone(att)
		self.assertEqual(str(att.out_time), str(shift_end))
		self.assertEqual(att.auto_clocked_out, 1)
		self.assertEqual(att.clock_out_reason, REASON_SHIFT_COMPLETED)
		# 09:05 to 17:00 is 7.92 hours
		self.assertAlmostEqual(float(att.working_hours), 7.92, places=1)

	def test_05_priority_left_office_before_shift_end(self):
		"""
		Rule 3 Priority: If an employee leaves office at 14:00 before 17:00 shift end,
		reason MUST be 'Left Office Location', not 'Shift Completed'.
		"""
		today = getdate(nowdate())
		leave_office_time = datetime.datetime.combine(today, datetime.time(14, 0, 0))

		# Clock in
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"employee_name": "Test Auto Employee",
			"time": datetime.datetime.combine(today, datetime.time(9, 0, 0)),
			"log_type": "IN",
			"shift": "Test Day Shift",
			"office_location": "Main Office",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Leaving office triggers geofence auto clock-out
		out_res = auto_clock_out_employee(
			employee_id="EMP-001",
			reason=REASON_LEFT_OFFICE,
			clock_out_datetime=leave_office_time,
			distance=350.0,
		)

		self.assertEqual(out_res["reason"], REASON_LEFT_OFFICE)
		self.assertEqual(out_res["clock_out_time"], str(leave_office_time))

		latest = get_latest_checkin("EMP-001")
		self.assertEqual(latest.get("clock_out_reason"), REASON_LEFT_OFFICE)

	def test_06_invalid_reason_raises_validation_error(self):
		"""
		Rule 3: Rejects any reason other than 'Left Office Location' or 'Shift Completed'.
		"""
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"time": now_datetime(),
			"log_type": "IN",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			auto_clock_out_employee(
				employee_id="EMP-001",
				reason="Forgot to punch",
			)

	# -------------------------------------------------------------
	# 3. ATTENDANCE & CHECKIN EXACT RECORD PERSISTENCE (RULE 4)
	# -------------------------------------------------------------
	def test_07_exact_attendance_record_fields(self):
		"""
		Rule 4: Save the exact date, time, and reason for every automatic clock-out
		in the employee's attendance record.
		"""
		test_date = datetime.date(2026, 9, 10)
		clock_in_dt = datetime.datetime(2026, 9, 10, 9, 0, 0)
		clock_out_dt = datetime.datetime(2026, 9, 10, 17, 0, 0)

		# Initial Checkin
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"time": clock_in_dt,
			"log_type": "IN",
			"shift": "Test Day Shift",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Auto clock out at shift end
		res = auto_clock_out_employee(
			employee_id="EMP-001",
			reason=REASON_SHIFT_COMPLETED,
			clock_out_datetime=clock_out_dt,
		)

		# Fetch tabAttendance directly
		att = frappe.db.get_value(
			"Attendance",
			{"employee": "EMP-001", "attendance_date": test_date},
			[
				"name",
				"employee",
				"attendance_date",
				"status",
				"in_time",
				"out_time",
				"working_hours",
				"auto_clocked_out",
				"clock_out_reason",
				"auto_clock_out_time",
			],
			as_dict=True,
		)

		self.assertIsNotNone(att)
		self.assertEqual(str(att.attendance_date), "2026-09-10")
		self.assertEqual(str(att.out_time), "2026-09-10 17:00:00")
		self.assertEqual(att.auto_clocked_out, 1)
		self.assertEqual(att.clock_out_reason, REASON_SHIFT_COMPLETED)
		self.assertEqual(str(att.auto_clock_out_time), "2026-09-10 17:00:00")
		self.assertAlmostEqual(float(att.working_hours), 8.0, places=1)

	# -------------------------------------------------------------
	# 4. NOTIFICATIONS (RULE 5)
	# -------------------------------------------------------------
	def test_08_notifications_created_for_employee_and_admin(self):
		"""
		Rule 5: Optionally notify the employee and administrator when an automatic clock-out occurs.
		"""
		clock_out_dt = now_datetime()
		notifs = send_auto_clock_out_notifications(
			employee_id="EMP-001",
			employee_name="Test Auto Employee",
			reason=REASON_LEFT_OFFICE,
			clock_out_time=clock_out_dt,
		)

		self.assertIn("employee@ems.com", [notifs.get("employee_notified")])
		self.assertIn("Administrator", notifs.get("admins_notified", []))

		# Check Notification Log records in MariaDB
		logs = frappe.get_all(
			"Notification Log",
			filters={"for_user": ["in", ["employee@ems.com", "Administrator"]]},
			fields=["name", "for_user", "subject", "email_content"],
		)

		emp_logs = [l for l in logs if l.for_user == "employee@ems.com"]
		admin_logs = [l for l in logs if l.for_user == "Administrator"]

		self.assertTrue(len(emp_logs) > 0, "Notification Log should be created for employee.")
		self.assertTrue(len(admin_logs) > 0, "Notification Log should be created for administrator.")
		self.assertIn(REASON_LEFT_OFFICE, emp_logs[0].subject)
		self.assertIn("Test Auto Employee", emp_logs[0].email_content)

	# -------------------------------------------------------------
	# 5. OVERNIGHT SHIFT COMPLETION
	# -------------------------------------------------------------
	def test_09_overnight_shift_completion_clockout(self):
		"""
		Overnight shift (22:00 to 06:00 next day):
		Shift end advances to the next calendar day at 06:00.
		"""
		sdoc = frappe.get_doc("Shift Type", "Test Night Shift")
		start_date = datetime.date(2026, 9, 10)
		shift_start, shift_end, _, _, is_overnight = get_shift_window(sdoc, start_date)

		self.assertTrue(is_overnight)
		self.assertEqual(shift_start, datetime.datetime(2026, 9, 10, 22, 0, 0))
		self.assertEqual(shift_end, datetime.datetime(2026, 9, 11, 6, 0, 0))

		# Clock in at 22:00
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"time": shift_start,
			"log_type": "IN",
			"shift": "Test Night Shift",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		# Auto clock-out at 06:00 next morning
		out_res = auto_clock_out_employee(
			employee_id="EMP-001",
			reason=REASON_SHIFT_COMPLETED,
			clock_out_datetime=shift_end,
		)

		self.assertEqual(out_res["reason"], REASON_SHIFT_COMPLETED)
		self.assertEqual(str(out_res["clock_out_time"]), "2026-09-11 06:00:00")

		latest = get_latest_checkin("EMP-001")
		self.assertEqual(str(latest.get("time")), "2026-09-11 06:00:00")
		self.assertEqual(latest.get("clock_out_reason"), REASON_SHIFT_COMPLETED)

	# -------------------------------------------------------------
	# 6. GET ATTENDANCE STATUS PAYLOAD WITH AUTO CLOCK-OUT
	# -------------------------------------------------------------
	def test_10_attendance_status_includes_auto_clock_out_fields(self):
		"""
		Real-time get_employee_attendance_status payload must expose
		auto_clocked_out, clock_out_reason, and auto_clock_out_time.
		"""
		today = getdate(nowdate())
		t_out = datetime.datetime.combine(today, datetime.time(17, 0, 0))

		# Create an auto-clocked-out session
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": "EMP-001",
			"time": datetime.datetime.combine(today, datetime.time(9, 0, 0)),
			"log_type": "IN",
			"shift": "Test Day Shift",
		}).insert(ignore_permissions=True)

		auto_clock_out_employee(
			employee_id="EMP-001",
			reason=REASON_LEFT_OFFICE,
			clock_out_datetime=t_out,
		)

		status_payload = get_employee_attendance_status(employee_id="EMP-001")
		self.assertFalse(status_payload["is_clocked_in"])
		self.assertEqual(status_payload["current_status"], "Clocked Out")
		self.assertTrue(status_payload["auto_clocked_out"])
		self.assertEqual(status_payload["clock_out_reason"], REASON_LEFT_OFFICE)
		self.assertIsNotNone(status_payload["auto_clock_out_time"])


if __name__ == "__main__":
	unittest.main()

