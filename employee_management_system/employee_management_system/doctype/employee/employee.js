// Copyright (c) 2026, veera and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
		// Custom status badge indicator
		if (frm.doc.status === "Active") {
			frm.set_df_property("status", "description", "Employee is currently active.");
		} else if (frm.doc.status === "On Leave") {
			frm.set_df_property("status", "description", "Employee is currently on approved leave.");
		}

		// Add custom action button to generate paystub preview
		if (!frm.is_new()) {
			frm.add_custom_button(__("View Quick Stats"), function () {
				frappe.call({
					method: "employee_management_system.employee_management_system.doctype.employee.employee.get_employee_details",
					args: {
						employee_id: frm.doc.name
					},
					callback: function (r) {
						if (r.message) {
							frappe.msgprint({
								title: __("Employee Quick Summary"),
								indicator: "blue",
								message: __("Full Name: <b>{0}</b><br>Department: <b>{1}</b><br>Basic Salary: <b>${2}</b>", [
									r.message.full_name,
									r.message.department || "N/A",
									r.message.basic_salary || 0
								])
							});
						}
					}
				});
			}, __("Actions"));
		}
	},

	validate(frm) {
		// 1. Full Name Validation
		if (!frm.doc.full_name || !frm.doc.full_name.trim()) {
			frappe.msgprint(__("Full Name is mandatory."));
			frappe.validated = false;
			return;
		}

		// 2. Email Validation
		if (frm.doc.email) {
			const email_regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
			if (!email_regex.test(frm.doc.email.trim())) {
				frappe.msgprint(__("Please enter a valid email address."));
				frappe.validated = false;
				return;
			}
		}

		// 3. Basic Salary Non-Negative Check
		if (frm.doc.basic_salary && flt(frm.doc.basic_salary) < 0) {
			frappe.msgprint(__("Basic Salary cannot be a negative value."));
			frappe.validated = false;
			return;
		}

		// 4. Phone Number Format Check
		if (frm.doc.phone && frm.doc.phone.length < 7) {
			frappe.msgprint(__("Please enter a valid phone number."));
			frappe.validated = false;
			return;
		}

		// 5. Date of Joining Validation
		if (frm.doc.date_of_joining) {
			const selected_date = new Date(frm.doc.date_of_joining);
			const max_future_date = new Date();
			max_future_date.setFullYear(max_future_date.getFullYear() + 1);

			if (selected_date > max_future_date) {
				frappe.msgprint(__("Date of Joining cannot be more than 1 year in the future."));
				frappe.validated = false;
				return;
			}
		}
	},

	department(frm) {
		// Auto-populate or suggest department head when department changes
		if (frm.doc.department) {
			frappe.db.get_value("Department", frm.doc.department, "department_head", (r) => {
				if (r && r.department_head && !frm.doc.reporting_manager) {
					frm.set_value("reporting_manager", r.department_head);
				}
			});
		}
	}
});
