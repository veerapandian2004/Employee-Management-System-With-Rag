# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
EMS SETUP & INITIALIZATION SCRIPT
==================================
Runs automatic database schema reload and seeds baseline enterprise data:
- DocTypes schema reloads
- Roles & Demo Users (Administrator, HR, Employee)
- Core Departments & Leave Types
- Shift Types (Day Shift & Night Shift)
- Sample Employees & Shift Assignments
- Corporate Policy Handbooks in tabHR Document
"""

import datetime
import frappe
from frappe.utils import getdate, nowdate


def run_setup():
	"""Main setup runner callable via bench execute or standalone python script."""
	print("=" * 60)
	print("Starting Employee Management System (EMS) Data Setup...")
	print("=" * 60)

	# 1. Reload all DocTypes
	print("\n[1/6] Reloading DocTypes schema into MariaDB...")
	doctypes = [
		"department",
		"employee",
		"leave_type",
		"leave_application",
		"salary_slip",
		"salary_slip_allowance",
		"salary_slip_deduction",
		"payroll",
		"office_location",
		"shift_type",
		"shift_assignment",
		"employee_checkin",
		"attendance",
		"chat_message",
		"chat_session",
		"holiday",
	]

	for dt in doctypes:
		try:
			frappe.reload_doc("employee_management_system", "doctype", dt, force=True)
			print(f"  ✓ Reloaded DocType: {dt}")
		except Exception as e:
			print(f"  ! Warning reloading {dt}: {e}")
	frappe.db.commit()

	# 2. Setup Roles
	print("\n[2/6] Configuring User Roles...")
	roles = ["HR", "HR Manager", "Employee", "System Manager"]
	for r in roles:
		if not frappe.db.exists("Role", r):
			frappe.get_doc({"doctype": "Role", "role_name": r}).insert(ignore_permissions=True)
			print(f"  ✓ Created Role: {r}")
		else:
			print(f"  - Role already exists: {r}")
	frappe.db.commit()

	# 3. Setup Demo Users
	print("\n[3/6] Configuring Demo Users...")
	from frappe.utils.password import update_password
	demo_users = [
		{
			"email": "admin@ems.com",
			"first_name": "Sarah",
			"last_name": "Jenkins",
			"roles": ["System Manager", "Administrator"],
			"password": "SarahJenkins",
		},
		{
			"email": "hr@ems.com",
			"first_name": "Alex",
			"last_name": "Rivera",
			"roles": ["HR Manager", "HR"],
			"password": "AlexRivera",
		},
		{
			"email": "employee@ems.com",
			"first_name": "David",
			"last_name": "Chen",
			"roles": ["Employee"],
			"password": "DavidChen",
		},
	]

	for u in demo_users:
		if not frappe.db.exists("User", u["email"]):
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": u["email"],
				"first_name": u["first_name"],
				"last_name": u["last_name"],
				"enabled": 1,
				"send_welcome_email": 0,
			})
			user_doc.insert(ignore_permissions=True)
			for r in u["roles"]:
				user_doc.add_roles(r)
			print(f"  ✓ Created User: {u['email']}")
		else:
			user_doc = frappe.get_doc("User", u["email"])
			user_doc.first_name = u["first_name"]
			user_doc.last_name = u["last_name"]
			user_doc.enabled = 1
			user_doc.save(ignore_permissions=True)
			for r in u["roles"]:
				if not frappe.db.exists("Has Role", {"parent": u["email"], "role": r}):
					user_doc.add_roles(r)
			print(f"  - Updated User: {u['email']}")
		update_password(u["email"], u["password"])
	frappe.db.commit()

	# 4. Setup Departments & Leave Types
	print("\n[4/6] Seeding Departments & Leave Types...")
	depts = ["Engineering", "Human Resources", "Finance", "Operations", "Marketing"]
	for d in depts:
		if not frappe.db.exists("Department", d):
			frappe.get_doc({
				"doctype": "Department",
				"department_name": d,
			}).insert(ignore_permissions=True)
			print(f"  ✓ Created Department: {d}")

	leave_types = [
		{"leave_type_name": "Sick Leave", "max_days_per_year": 12, "carry_forward": 0},
		{"leave_type_name": "Casual Leave", "max_days_per_year": 14, "carry_forward": 0},
		{"leave_type_name": "Annual Leave", "max_days_per_year": 20, "carry_forward": 1},
	]
	for lt in leave_types:
		if not frappe.db.exists("Leave Type", lt["leave_type_name"]):
			frappe.get_doc({
				"doctype": "Leave Type",
				**lt,
			}).insert(ignore_permissions=True)
			print(f"  ✓ Created Leave Type: {lt['leave_type_name']}")
	frappe.db.commit()

	# 5. Setup Office Locations
	print("\n[5/7] Seeding Office Locations...")
	offices = [
		{
			"doctype": "Office Location",
			"office_name": "Techunison Software India Pvt Ltd",
			"latitude": 11.057199,
			"longitude": 76.944784,
			"allowed_radius": 150.0,
			"max_accuracy": 50.0,
			"is_active": 1,
			"address": "77, 3rd St, MKG Layout, Gounder Mills, Coimbatore, Tamil Nadu 641029",
		},
		{
			"doctype": "Office Location",
			"office_name": "Chennai Office",
			"latitude": 13.0827,
			"longitude": 80.2707,
			"allowed_radius": 200.0,
			"max_accuracy": 50.0,
			"is_active": 1,
			"address": "Tidel Park, Tharamani, Chennai, Tamil Nadu",
		},
		{
			"doctype": "Office Location",
			"office_name": "Bangalore Office",
			"latitude": 12.9716,
			"longitude": 77.5946,
			"allowed_radius": 200.0,
			"max_accuracy": 50.0,
			"is_active": 1,
			"address": "Electronic City Phase 1, Bangalore, Karnataka",
		},
	]
	for o in offices:
		if not frappe.db.exists("Office Location", o["office_name"]):
			frappe.get_doc(o).insert(ignore_permissions=True)
			print(f"  ✓ Created Office Location: {o['office_name']}")
		else:
			frappe.db.set_value("Office Location", o["office_name"], {
				"latitude": o["latitude"],
				"longitude": o["longitude"],
				"allowed_radius": o["allowed_radius"],
				"max_accuracy": o["max_accuracy"],
				"address": o.get("address"),
			})
			print(f"  - Updated Office Location: {o['office_name']}")
	frappe.db.commit()

	# 6. Setup Shift Types
	print("\n[6/7] Seeding Shift Types...")
	shifts = [
		{
			"doctype": "Shift Type",
			"shift_name": "Day Shift",
			"start_time": "09:00:00",
			"end_time": "17:00:00",
			"enable_auto_attendance": 1,
			"late_entry_grace_period": 15,
			"early_exit_grace_period": 15,
			"working_hours_threshold_for_half_day": 4.0,
			"working_hours_threshold_for_absent": 1.0,
			"working_hours_threshold_for_present": 8.0,
			"begin_check_in_before_shift_start_time": 60,
			"allow_check_out_after_shift_end_time": 60,
			"weekly_off_days": "Saturday, Sunday",
			"is_active": 1,
			"description": "Standard Day Shift 9 AM to 5 PM",
		},
		{
			"doctype": "Shift Type",
			"shift_name": "Night Shift",
			"start_time": "22:00:00",
			"end_time": "06:00:00",
			"enable_auto_attendance": 1,
			"late_entry_grace_period": 15,
			"early_exit_grace_period": 15,
			"working_hours_threshold_for_half_day": 4.0,
			"working_hours_threshold_for_absent": 1.0,
			"working_hours_threshold_for_present": 8.0,
			"begin_check_in_before_shift_start_time": 60,
			"allow_check_out_after_shift_end_time": 60,
			"weekly_off_days": "Saturday, Sunday",
			"is_active": 1,
			"description": "Overnight Shift 10 PM to 6 AM (Next Day)",
		},
	]
	for s in shifts:
		if not frappe.db.exists("Shift Type", s["shift_name"]):
			frappe.get_doc(s).insert(ignore_permissions=True)
			print(f"  ✓ Created Shift Type: {s['shift_name']}")
		else:
			frappe.db.set_value("Shift Type", s["shift_name"], {
				"weekly_off_days": s["weekly_off_days"],
				"is_active": s["is_active"],
			})
			print(f"  - Updated Shift Type: {s['shift_name']}")
	frappe.db.commit()

	# 6b. Setup Holidays
	print("\n[6b/7] Seeding Company Holidays...")
	holidays = [
		{"holiday_date": "2026-01-01", "holiday_name": "New Year's Day", "description": "Global New Year Celebration"},
		{"holiday_date": "2026-01-26", "holiday_name": "Republic Day", "description": "National Holiday"},
		{"holiday_date": "2026-05-01", "holiday_name": "Labour Day", "description": "International Workers' Day"},
		{"holiday_date": "2026-08-15", "holiday_name": "Independence Day", "description": "National Holiday"},
		{"holiday_date": "2026-10-02", "holiday_name": "Gandhi Jayanti", "description": "National Holiday"},
		{"holiday_date": "2026-12-25", "holiday_name": "Christmas Day", "description": "Christmas Celebration"},
	]
	for h in holidays:
		if not frappe.db.exists("Holiday", h["holiday_date"]):
			frappe.get_doc({"doctype": "Holiday", **h}).insert(ignore_permissions=True)
			print(f"  ✓ Created Holiday: {h['holiday_name']} ({h['holiday_date']})")
		else:
			print(f"  - Holiday already exists: {h['holiday_name']}")
	frappe.db.commit()

	# 7. Setup Sample Employees & Shift Assignment
	print("\n[7/7] Seeding Sample Employees & Shift Assignments...")
	if not frappe.db.exists("Employee", "EMP-001"):
		emp1 = frappe.get_doc({
			"doctype": "Employee",
			"naming_series": "EMP-001",
			"full_name": "Sarah Jenkins",
			"email": "employee@ems.com",
			"phone": "+1-555-0192",
			"department": "Engineering",
			"designation": "Senior Full-Stack Engineer",
			"date_of_joining": "2024-01-15",
			"employment_type": "Full-Time",
			"status": "Active",
			"basic_salary": 9500.0,
			"user_id": "employee@ems.com",
			"office_location": "Main Office",
		})
		emp1.insert(ignore_permissions=True)
		print("  ✓ Created Employee: EMP-001 Sarah Jenkins")
	else:
		frappe.db.set_value("Employee", "EMP-001", "office_location", "Main Office")

	if not frappe.db.exists("Employee", "EMP-002"):
		emp2 = frappe.get_doc({
			"doctype": "Employee",
			"naming_series": "EMP-002",
			"full_name": "Alex Rivera",
			"email": "alex.rivera@ems.com",
			"phone": "+1-555-0193",
			"department": "Human Resources",
			"designation": "HR Specialist",
			"date_of_joining": "2024-03-01",
			"employment_type": "Full-Time",
			"status": "Active",
			"basic_salary": 7200.0,
			"user_id": "hr@ems.com",
			"office_location": "Main Office",
		})
		emp2.insert(ignore_permissions=True)
		print("  ✓ Created Employee: EMP-002 Alex Rivera")
	else:
		frappe.db.set_value("Employee", "EMP-002", "office_location", "Main Office")

	# Shift Assignment for EMP-001
	if not frappe.db.exists("Shift Assignment", {"employee": "EMP-001", "shift_type": "Day Shift"}):
		frappe.get_doc({
			"doctype": "Shift Assignment",
			"employee": "EMP-001",
			"shift_type": "Day Shift",
			"start_date": "2026-01-01",
			"status": "Active",
		}).insert(ignore_permissions=True)
		print("  ✓ Assigned Shift: EMP-001 -> Day Shift")

	frappe.db.commit()

	print("\n" + "=" * 60)
	print("EMS Setup Completed Successfully!")
	print("Demo Logins:")
	print("  • Administrator: admin@ems.com    / SarahJenkins (or Administrator / admin)")
	print("  • HR Manager:    hr@ems.com       / AlexRivera")
	print("  • Employee:      employee@ems.com / DavidChen")
	print("=" * 60)


if __name__ == "__main__":
	if not frappe.db:
		frappe.init(site="hospital.localhost")
		frappe.connect()
	run_setup()

