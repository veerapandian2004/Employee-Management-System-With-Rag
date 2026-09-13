// Frappe Backend API Service

const BASE_URL = "";

function getCsrfToken() {
  if (typeof document !== "undefined" && document.cookie) {
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    if (match) return decodeURIComponent(match[1]);
  }
  if (typeof window !== "undefined" && window.csrf_token && window.csrf_token !== "{{ csrf_token }}") {
    return window.csrf_token;
  }
  return null;
}

export function getHeaders(extraHeaders = {}) {
  const headers = {
    Accept: "application/json",
    ...extraHeaders,
  };
  const token = getCsrfToken();
  if (token) {
    headers["X-Frappe-CSRF-Token"] = token;
  }
  return headers;
}

function extractFrappeErrorMessage(errJson, fallbackStatus) {
  if (!errJson) return `API Error ${fallbackStatus || ""}`.trim();
  if (errJson._server_messages) {
    try {
      const messages = typeof errJson._server_messages === "string"
        ? JSON.parse(errJson._server_messages)
        : errJson._server_messages;
      if (Array.isArray(messages) && messages.length > 0) {
        const first = typeof messages[0] === "string" ? JSON.parse(messages[0]) : messages[0];
        if (first && first.message) {
          return first.message.replace(/<[^>]*>?/gm, "").trim();
        }
      }
    } catch {
      // ignore JSON parse error
    }
  }
  if (errJson.exception) {
    return errJson.exception.split(":").pop().trim();
  }
  if (errJson.message) {
    return typeof errJson.message === "string" ? errJson.message : JSON.stringify(errJson.message);
  }
  return `API Error ${fallbackStatus || ""}`.trim();
}

async function handleResponse(res) {
  if (!res.ok) {
    let errMsg = `API Error ${res.status}`;
    try {
      const errJson = await res.json();
      errMsg = extractFrappeErrorMessage(errJson, res.status);
    } catch {
      const errText = await res.text();
      if (errText) errMsg = errText;
    }
    throw new Error(errMsg);
  }
  const json = await res.json();
  if (json && (json.exc || json.exception)) {
    throw new Error(extractFrappeErrorMessage(json, 200));
  }
  return json.message !== undefined ? json.message : (json.data !== undefined ? json.data : json);
}


// ---------------- AUTHENTICATION ----------------
export async function apiLogin(usr, pwd) {
  const res = await fetch(`${BASE_URL}/api/method/login`, {
    method: "POST",
    headers: getHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({ usr, pwd })
  });
  return await handleResponse(res);
}

export async function apiLogout() {
  try {
    const res = await fetch(`${BASE_URL}/api/method/logout`, {
      method: "POST",
      headers: getHeaders(),
      credentials: "include"
    });
    return await handleResponse(res);
  } catch (err) {
    console.warn("Logout error:", err);
    return true;
  }
}

export async function apiGetCurrentUser() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_current_user`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to get current user:", err);
    return {
      user: "Guest",
      full_name: "Guest",
      role: "Guest",
      roles: ["Guest"],
      employee: null,
      is_logged_in: false
    };
  }
}

// ---------------- EMPLOYEE ----------------
export async function apiFetchEmployees() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_employees`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Employees:", err);
    return [];
  }
}

export async function apiCreateEmployee(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_employee`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateEmployee(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_employee`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteEmployee(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_employee`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

// ---------------- DEPARTMENT ----------------
export async function apiFetchDepartments() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_departments`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Departments:", err);
    return [];
  }
}

export async function apiCreateDepartment(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_department`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateDepartment(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_department`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteDepartment(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_department`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

// ---------------- ATTENDANCE ----------------
export async function apiFetchAttendance() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_attendance`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Attendance:", err);
    return [];
  }
}

export async function apiCreateAttendance(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_attendance`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateAttendance(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_attendance`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteAttendance(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_attendance`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

export async function apiEmployeeCheckin(employee = null, timestamp = null, log_type = "IN", device_id = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.employee_checkin`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ employee, timestamp, log_type, device_id })
    }
  );
  return await handleResponse(res);
}

export async function apiEmployeeCheckout(employee = null, timestamp = null, device_id = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.employee_checkout`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ employee, timestamp, device_id })
    }
  );
  return await handleResponse(res);
}

export async function apiClockIn({ latitude, longitude, accuracy }) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.clock_in`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ latitude, longitude, accuracy }),
    }
  );
  return await handleResponse(res);
}

export async function apiClockOut({ latitude, longitude, accuracy }) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.clock_out`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ latitude, longitude, accuracy }),
    }
  );
  return await handleResponse(res);
}

export async function apiPingLocation({ latitude, longitude, accuracy }) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.ping_location`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ latitude, longitude, accuracy }),
    }
  );
  return await handleResponse(res);
}

export async function apiTriggerShiftCompletionClockout() {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.trigger_shift_completion_clockout`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
    }
  );
  return await handleResponse(res);
}

export async function apiGetAutoClockoutLogs(employee = null, fromDate = null, toDate = null) {
  const params = new URLSearchParams();
  if (employee) params.append("employee", employee);
  if (fromDate) params.append("from_date", fromDate);
  if (toDate) params.append("to_date", toDate);
  const q = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_auto_clockout_logs${q}`,
    {
      headers: getHeaders(),
      credentials: "include",
    }
  );
  return await handleResponse(res);
}

export async function apiGetMyAttendanceStatus() {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_my_attendance_status`,
    {
      headers: getHeaders(),
      credentials: "include",
    }
  );
  return await handleResponse(res);
}

export async function apiGetMyAttendance(fromDate = null, toDate = null) {
  const params = new URLSearchParams();
  if (fromDate) params.append("from_date", fromDate);
  if (toDate) params.append("to_date", toDate);
  const q = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_my_attendance${q}`,
    {
      headers: getHeaders(),
      credentials: "include",
    }
  );
  return await handleResponse(res);
}

export async function apiFetchOfficeLocations() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_office_locations`,
      {
        headers: getHeaders(),
        credentials: "include",
      }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch office locations:", err);
    return [];
  }
}

export async function apiRecalculateAttendance(attendance_date = null, shift_type = null, employee = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.recalculate_attendance`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ attendance_date, shift_type, employee })
    }
  );
  return await handleResponse(res);
}

export async function apiFetchShiftTypes() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_shift_types`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Shift Types:", err);
    return [];
  }
}

export async function apiFetchShiftAssignments(employee = null) {
  try {
    const url = employee
      ? `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_shift_assignments?employee=${encodeURIComponent(employee)}`
      : `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_shift_assignments`;
    const res = await fetch(url, { headers: getHeaders(), credentials: "include" });
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Shift Assignments:", err);
    return [];
  }
}

export async function apiFetchCheckins(employee = null, from_date = null, to_date = null) {
  try {
    const params = new URLSearchParams();
    if (employee) params.append("employee", employee);
    if (from_date) params.append("from_date", from_date);
    if (to_date) params.append("to_date", to_date);
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_employee_checkins?${params.toString()}`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch checkins:", err);
    return [];
  }
}

export async function apiCreateShiftType(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_shift_type`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateShiftType(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_shift_type`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteShiftType(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_shift_type`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

export async function apiCreateShiftAssignment(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_shift_assignment`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateShiftAssignment(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_shift_assignment`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteShiftAssignment(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_shift_assignment`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

export async function apiFetchHolidays(year = null) {
  try {
    const url = year
      ? `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_holidays?year=${encodeURIComponent(year)}`
      : `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_holidays`;
    const res = await fetch(url, { headers: getHeaders(), credentials: "include" });
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch holidays:", err);
    return [];
  }
}

export async function apiCreateHoliday(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_holiday`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteHoliday(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_holiday`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}


// ---------------- LEAVE APPLICATION ----------------
export async function apiFetchLeaveApplications() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_leave_applications`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Leave Applications:", err);
    return [];
  }
}

export async function apiCreateLeaveApplication(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_leave_application`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateLeaveStatus(name, status) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_leave_status`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, status })
    }
  );
  return await handleResponse(res);
}

export async function apiCancelLeaveApplication(name, reason = "") {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.cancel_leave_application`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, reason })
    }
  );
  return await handleResponse(res);
}

export async function apiGetLeaveBalance(employee, leaveType) {
  try {
    const params = new URLSearchParams({ employee, leave_type: leaveType });
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_leave_balance?${params.toString()}`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch leave balance:", err);
    return null;
  }
}

export async function apiDeleteLeaveApplication(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_leave_application`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

// ---------------- LEAVE TYPE ----------------
export async function apiFetchLeaveTypes() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_leave_types`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Leave Types:", err);
    return [];
  }
}

export async function apiCreateLeaveType(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_leave_type`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateLeaveType(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_leave_type`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteLeaveType(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_leave_type`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

// ---------------- SALARY SLIP ----------------
export async function apiFetchSalarySlips() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_salary_slips`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Salary Slips:", err);
    return [];
  }
}

export async function apiCreateSalarySlip(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_salary_slip`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdateSalarySlip(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_salary_slip`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteSalarySlip(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_salary_slip`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

export async function apiCalculateLop(employee, salaryMonth) {
  try {
    const params = new URLSearchParams({ employee, salary_month: salaryMonth });
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.calculate_lop_for_employee_month?${params.toString()}`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to calculate LOP:", err);
    return null;
  }
}

export async function apiDownloadSalarySlipPdf(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.download_salary_slip_pdf?name=${encodeURIComponent(name)}`,
    { headers: getHeaders(), credentials: "include" }
  );
  if (!res.ok) {
    throw new Error(`Failed to download PDF: ${res.statusText}`);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Salary_Slip_${name}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function apiSendSalarySlipEmail(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.send_salary_slip_email`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}

export async function apiSendBatchSalarySlipEmails(salaryMonth = null, department = null, retryFailedOnly = false) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.send_batch_salary_slip_emails`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({
        salary_month: salaryMonth,
        department: department,
        retry_failed_only: retryFailedOnly
      })
    }
  );
  return await handleResponse(res);
}

// ---------------- PAYROLL ----------------
export async function apiFetchPayrolls() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_payrolls`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Payrolls:", err);
    return [];
  }
}

export async function apiFetchPayrollRuns() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_payroll_runs`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch payroll runs:", err);
    return [];
  }
}

export async function apiGenerateBatchPayroll(params) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.generate_batch_payroll`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify(params)
    }
  );
  return await handleResponse(res);
}

export async function apiCreatePayroll(data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_payroll`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ data })
    }
  );
  return await handleResponse(res);
}

export async function apiUpdatePayroll(name, data) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.update_payroll`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name, data })
    }
  );
  return await handleResponse(res);
}

export async function apiDeletePayroll(name) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_payroll`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ name })
    }
  );
  return await handleResponse(res);
}


// ---------------- CHAT ASSISTANT ----------------
export async function apiSendChatMessage(message, conversationContext = null, conversationId = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.send_chat_message`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({
        message,
        conversation_context: conversationContext,
        conversation_id: conversationId,
      })
    }
  );
  return await handleResponse(res);
}

export async function apiFetchChatHistory(conversationId = null) {
  try {
    const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_chat_history${query}`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch Chat History:", err);
    return [];
  }
}

export async function apiRouteChatIntent(message, conversationContext = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.route_chat_intent`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ message, conversation_context: conversationContext }),
    }
  );
  return await handleResponse(res);
}

export async function apiGetIntentRouterPrompt() {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_intent_router_prompt`,
    { headers: getHeaders(), credentials: "include" }
  );
  return await handleResponse(res);
}

export async function apiGetSqlGeneratorPrompt() {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_sql_generator_prompt`,
    { headers: getHeaders(), credentials: "include" }
  );
  return await handleResponse(res);
}

export async function apiGetResultFormatterPrompt() {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_result_formatter_prompt`,
    { headers: getHeaders(), credentials: "include" }
  );
  return await handleResponse(res);
}

export async function apiFormatDatabaseResult(userQuestion, databaseResult, conversationContext = null, llmResponse = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.format_database_result_api`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({
        user_question: userQuestion,
        database_result: databaseResult,
        conversation_context: conversationContext,
        llm_response: llmResponse,
      }),
    }
  );
  return await handleResponse(res);
}


// ---------------- NOTIFICATIONS ----------------
export async function apiFetchNotifications(limit = 30) {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_notifications?limit=${encodeURIComponent(limit)}`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch notifications:", err);
    return { notifications: [], unread_count: 0 };
  }
}

export async function apiMarkNotificationRead(notificationName) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.mark_notification_read`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ notification_name: notificationName })
    }
  );
  return await handleResponse(res);
}

export async function apiMarkAllNotificationsRead() {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.mark_all_notifications_read`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include"
    }
  );
  return await handleResponse(res);
}


// ---------------- CHAT SESSIONS ----------------
export async function apiFetchChatSessions() {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_chat_sessions`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch chat sessions:", err);
    return [];
  }
}

export async function apiCreateChatSession(title = null, initialMessages = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.create_chat_session`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ title, initial_messages: initialMessages })
    }
  );
  return await handleResponse(res);
}

export async function apiFetchChatSessionMessages(sessionId) {
  try {
    const res = await fetch(
      `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.get_chat_session_messages?session_id=${encodeURIComponent(sessionId)}`,
      { headers: getHeaders(), credentials: "include" }
    );
    return await handleResponse(res);
  } catch (err) {
    console.error("Failed to fetch session messages:", err);
    return [];
  }
}

export async function apiSaveChatSession(sessionId, messages = null, title = null) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.save_chat_session`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ session_id: sessionId, messages, title })
    }
  );
  return await handleResponse(res);
}

export async function apiDeleteChatSession(sessionId) {
  const res = await fetch(
    `${BASE_URL}/api/method/employee_management_system.employee_management_system.api.delete_chat_session`,
    {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ session_id: sessionId })
    }
  );
  return await handleResponse(res);
}


