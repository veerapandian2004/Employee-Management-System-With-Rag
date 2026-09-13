# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import math
import os
import sys
import unittest
import frappe
from frappe.utils import nowdate, now_datetime

app_root = "/home/tui013/frappe-benchv/apps/employee_management_system"
if app_root in sys.path:
	sys.path.remove(app_root)
sys.path.insert(0, app_root)
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir in sys.path:
	sys.path.remove(cur_dir)

# Ensure sites environment is loaded
if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.attendance.gps_validation import (
	validate_coordinates,
	haversine_distance,
	validate_gps_accuracy,
	validate_office_radius,
)
from employee_management_system.employee_management_system.attendance.checkin_service import (
	get_authenticated_employee,
	get_assigned_office,
	get_latest_checkin,
	validate_checkin_sequence,
	record_gps_checkin,
	get_employee_attendance_status,
)
from employee_management_system.employee_management_system.api import (
	clock_in,
	clock_out,
	get_my_attendance_status,
	get_my_attendance,
	get_office_locations,
)


class TestGpsAttendance(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		# Ensure Main Office exists
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
			})

		# Ensure EMP-001 exists and is assigned to Main Office
		if frappe.db.exists("Employee", "EMP-001"):
			frappe.db.set_value("Employee", "EMP-001", "office_location", "Main Office")
			frappe.db.set_value("Employee", "EMP-001", "status", "Active")
			frappe.db.set_value("Employee", "EMP-001", "user_id", "employee@ems.com")

		# Ensure Day Shift assigned
		if not frappe.db.exists("Shift Assignment", {"employee": "EMP-001", "shift_type": "Day Shift"}):
			frappe.get_doc({
				"doctype": "Shift Assignment",
				"employee": "EMP-001",
				"shift_type": "Day Shift",
				"start_date": "2026-01-01",
				"status": "Active",
			}).insert(ignore_permissions=True)

		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		# Clean up any checkins for test employee
		frappe.db.sql("DELETE FROM `tabEmployee Checkin` WHERE employee = 'EMP-001'")
		frappe.db.sql("DELETE FROM `tabAttendance` WHERE employee = 'EMP-001'")
		frappe.db.commit()
		frappe.set_user("employee@ems.com")

	def tearDown(self):
		frappe.set_user("Administrator")

	# -------------------------------------------------------------
	# 1. HAVERSINE DISTANCE FORMULA
	# -------------------------------------------------------------
	def test_01_haversine_distance_calculation(self):
		"""Haversine distance calculations against known benchmark points."""
		# Distance to same point must be 0
		d_zero = haversine_distance(11.057199, 76.944784, 11.057199, 76.944784)
		self.assertEqual(d_zero, 0.0)

		# Very close point (~46.7 meters)
		d_close = haversine_distance(11.057199, 76.944784, 11.057499, 76.945084)
		self.assertTrue(40.0 <= d_close <= 55.0, f"Expected ~46m, got {d_close}")

		# Distant point (~2.4 km along latitude)
		d_far = haversine_distance(11.057199, 76.944784, 11.078799, 76.944784)
		self.assertTrue(2300.0 <= d_far <= 2500.0, f"Expected ~2400m, got {d_far}")

		# Coimbatore (11.057199, 76.944784) to Chennai (13.0827, 80.2707) ~428 km
		d_city = haversine_distance(11.057199, 76.944784, 13.0827, 80.2707)
		self.assertTrue(420000.0 <= d_city <= 435000.0, f"Expected ~428km, got {d_city}m")

	# -------------------------------------------------------------
	# 2. COORDINATE VALIDATION
	# -------------------------------------------------------------
	def test_02_validate_coordinates_valid(self):
		lat, lon = validate_coordinates(11.057199, 76.944784)
		self.assertAlmostEqual(lat, 11.057199)
		self.assertAlmostEqual(lon, 76.944784)

		# Strings convertible to float
		lat_s, lon_s = validate_coordinates("13.0827", "80.2707")
		self.assertAlmostEqual(lat_s, 13.0827)
		self.assertAlmostEqual(lon_s, 80.2707)

	def test_03_validate_coordinates_invalid(self):
		with self.assertRaises(frappe.ValidationError):
			validate_coordinates(None, 76.944784)

		with self.assertRaises(frappe.ValidationError):
			validate_coordinates("invalid_lat", 76.944784)

		with self.assertRaises(frappe.ValidationError):
			validate_coordinates(95.0, 76.944784)  # Latitude > 90

		with self.assertRaises(frappe.ValidationError):
			validate_coordinates(11.057199, 190.0)  # Longitude > 180

	# -------------------------------------------------------------
	# 3. GPS ACCURACY VALIDATION
	# -------------------------------------------------------------
	def test_04_validate_gps_accuracy_pass(self):
		# Within 50m max accuracy
		acc = validate_gps_accuracy(12.5, max_accuracy=50.0)
		self.assertEqual(acc, 12.5)

		acc_boundary = validate_gps_accuracy(50.0, max_accuracy=50.0)
		self.assertEqual(acc_boundary, 50.0)

	def test_05_validate_gps_accuracy_reject(self):
		# Worse than 50m threshold (e.g. 51m or 85m)
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_gps_accuracy(85.0, max_accuracy=50.0)
		self.assertIn("Location accuracy is too low", str(ctx.exception))

	# -------------------------------------------------------------
	# 4. OFFICE RADIUS VALIDATION
	# -------------------------------------------------------------
	def test_06_validate_office_radius_inside(self):
		# Point 46.7 meters from Main Office (11.057199, 76.944784) with 150m allowed radius
		dist = validate_office_radius(
			emp_lat=11.057499,
			emp_lon=76.945084,
			office_lat=11.057199,
			office_lon=76.944784,
			allowed_radius=150.0,
			office_name="Main Office",
		)
		self.assertTrue(dist <= 150.0)

	def test_07_validate_office_radius_outside(self):
		# Point 2.4km from Main Office
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_office_radius(
				emp_lat=11.078799,
				emp_lon=76.944784,
				office_lat=11.057199,
				office_lon=76.944784,
				allowed_radius=150.0,
				office_name="Main Office",
			)
		self.assertIn("outside the authorized office radius", str(ctx.exception))

	# -------------------------------------------------------------
	# 5. AUTHENTICATED EMPLOYEE RESOLUTION
	# -------------------------------------------------------------
	def test_08_authenticated_employee_resolution(self):
		emp = get_authenticated_employee(user="employee@ems.com")
		self.assertEqual(emp.name, "EMP-001")
		self.assertEqual(emp.status, "Active")

	def test_09_guest_user_rejected(self):
		with self.assertRaises(frappe.AuthenticationError):
			get_authenticated_employee(user="Guest")

	def test_10_inactive_employee_rejected(self):
		frappe.db.set_value("Employee", "EMP-001", "status", "Inactive")
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError) as ctx:
			get_authenticated_employee(user="employee@ems.com")
		self.assertIn("Only active employees can record attendance", str(ctx.exception))
		# Restore
		frappe.db.set_value("Employee", "EMP-001", "status", "Active")
		frappe.db.commit()

	# -------------------------------------------------------------
	# 6. IN/OUT SEQUENCE VALIDATION
	# -------------------------------------------------------------
	def test_11_checkin_sequence_validation(self):
		# Initially no checkins: IN is allowed, OUT is rejected
		self.assertTrue(validate_checkin_sequence("EMP-001", "IN"))
		with self.assertRaises(frappe.ValidationError):
			validate_checkin_sequence("EMP-001", "OUT")

	# -------------------------------------------------------------
	# 7. CLOCK IN & DUPLICATE PREVENTION
	# -------------------------------------------------------------
	def test_12_clock_in_success(self):
		# Submitting position at office (lat: 11.057199, lon: 76.944784, acc: 15m)
		res = clock_in(latitude=11.057199, longitude=76.944784, accuracy=15.0)
		self.assertIsNotNone(res.get("checkin"))
		checkin = res["checkin"]
		self.assertEqual(checkin["employee"], "EMP-001")
		self.assertEqual(checkin["log_type"], "IN")
		self.assertEqual(checkin["attendance_source"], "GPS Web Clock")
		self.assertAlmostEqual(float(checkin["latitude"]), 11.057199)
		self.assertAlmostEqual(float(checkin["longitude"]), 76.944784)
		self.assertEqual(checkin["office_location"], "Main Office")
		self.assertTrue(float(checkin["distance_from_office"]) <= 150.0)

	def test_13_clock_in_duplicate_prevention(self):
		# First clock in succeeds
		clock_in(latitude=11.057199, longitude=76.944784, accuracy=15.0)

		# Second clock in without clocking out must be rejected
		with self.assertRaises(frappe.ValidationError) as ctx:
			clock_in(latitude=11.057199, longitude=76.944784, accuracy=15.0)
		self.assertIn("already clocked in", str(ctx.exception).lower())

	# -------------------------------------------------------------
	# 8. CLOCK OUT & REJECTION OF OUT WITHOUT IN
	# -------------------------------------------------------------
	def test_14_clock_out_without_clock_in_rejected(self):
		# No active check-in session exists
		with self.assertRaises(frappe.ValidationError) as ctx:
			clock_out(latitude=11.057199, longitude=76.944784, accuracy=15.0)
		self.assertIn("Cannot clock OUT without an active clock IN session", str(ctx.exception))

	def test_15_clock_out_success(self):
		# Clock IN
		clock_in(latitude=11.057199, longitude=76.944784, accuracy=15.0)

		# Clock OUT
		res = clock_out(latitude=11.057199, longitude=76.944784, accuracy=15.0)
		self.assertIsNotNone(res.get("checkin"))
		checkin = res["checkin"]
		self.assertEqual(checkin["employee"], "EMP-001")
		self.assertEqual(checkin["log_type"], "OUT")
		self.assertEqual(checkin["attendance_source"], "GPS Web Clock")

		# Immediate second Clock OUT must be rejected (OUT -> OUT)
		with self.assertRaises(frappe.ValidationError) as ctx:
			clock_out(latitude=11.057199, longitude=76.944784, accuracy=15.0)
		self.assertIn("Cannot clock OUT without an active clock IN session", str(ctx.exception))

	# -------------------------------------------------------------
	# 9. LOW ACCURACY & OUTSIDE RADIUS REJECTIONS
	# -------------------------------------------------------------
	def test_16_clock_in_low_accuracy_rejected(self):
		# Correct office coordinates, but poor accuracy reading (85m > 50m max)
		with self.assertRaises(frappe.ValidationError) as ctx:
			clock_in(latitude=11.057199, longitude=76.944784, accuracy=85.0)
		self.assertIn("Location accuracy is too low", str(ctx.exception))

	def test_17_clock_in_outside_office_radius_rejected(self):
		# Accurate GPS reading (10m), but location is 2.4km away from office
		with self.assertRaises(frappe.ValidationError) as ctx:
			clock_in(latitude=11.078799, longitude=76.944784, accuracy=10.0)
		self.assertIn("outside the authorized office radius", str(ctx.exception))

	# -------------------------------------------------------------
	# 10. REAL-TIME ATTENDANCE STATUS API
	# -------------------------------------------------------------
	def test_18_get_my_attendance_status(self):
		status = get_my_attendance_status()
		self.assertEqual(status["employee"], "EMP-001")
		self.assertFalse(status["is_clocked_in"])
		self.assertEqual(status["current_status"], "Not Clocked In")
		self.assertEqual(status["office"]["name"], "Main Office")
		self.assertIsNotNone(status["today_shift"])

		# Clock in and recheck status
		clock_in(latitude=11.057199, longitude=76.944784, accuracy=15.0)
		status_after = get_my_attendance_status()
		self.assertTrue(status_after["is_clocked_in"])
		self.assertEqual(status_after["current_status"], "Working")
		self.assertIsNotNone(status_after["clock_in_time"])

	# -------------------------------------------------------------
	# 11. GET OFFICE LOCATIONS API
	# -------------------------------------------------------------
	def test_19_get_office_locations(self):
		offices = get_office_locations()
		self.assertTrue(len(offices) >= 1)
		names = [o["office_name"] for o in offices]
		self.assertIn("Main Office", names)


if __name__ == "__main__":
	unittest.main(verbosity=2)
