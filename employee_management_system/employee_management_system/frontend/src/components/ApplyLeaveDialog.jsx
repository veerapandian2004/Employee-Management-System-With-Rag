import { useState, useEffect } from "react";
import { AlertCircle, CalendarCheck, Info } from "lucide-react";
import { Dialog } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Select } from "./ui/select";
import { apiGetLeaveBalance } from "../services/apiService";

export function ApplyLeaveDialog({
  isOpen,
  onClose,
  onAddLeaveApplication,
  leaveTypes = [],
  employees = [],
  userRole = "Employee",
  currentUser = null,
}) {
  const isAdmin = userRole === "Administrator";
  const canApprove = isAdmin || userRole === "HR";

  const adminEmpId = (currentUser?.employee?.name || currentUser?.employee?.naming_series || "EMP-001").trim();
  const adminUser = (currentUser?.user || "admin@ems.com").toLowerCase().trim();
  const adminEmail = (currentUser?.email || currentUser?.employee?.email || "admin@ems.com").toLowerCase().trim();

  const isAdminRecord = (emp) => {
    if (!emp) return false;
    const id = (emp.name || emp.naming_series || "").trim();
    const userId = (emp.user_id || "").toLowerCase().trim();
    const email = (emp.email || "").toLowerCase().trim();
    return (
      id === adminEmpId ||
      id === "EMP-001" ||
      userId === "administrator" ||
      userId === "admin@ems.com" ||
      userId === adminUser ||
      email === "admin@ems.com" ||
      email === adminEmail
    );
  };

  // If Admin, do not allow Admin's own record in the selectable employees list
  const selectableEmployees = isAdmin
    ? employees.filter((emp) => !isAdminRecord(emp))
    : employees;

  // For Admin, default to the first selectable staff member. For others, default to their own record.
  const defaultEmp = isAdmin
    ? (selectableEmployees[0] || null)
    : (currentUser?.employee || employees[0] || null);

  const defaultEmpId = defaultEmp ? (defaultEmp.naming_series || defaultEmp.name) : "";
  const defaultEmpName = defaultEmp ? defaultEmp.full_name : "";

  const initialForm = {
    employee: defaultEmpId,
    employee_name: defaultEmpName,
    leave_type: leaveTypes[0]?.leave_type_name || leaveTypes[0]?.name || "Annual Leave",
    from_date: new Date().toISOString().split("T")[0],
    to_date: new Date().toISOString().split("T")[0],
    total_days: 1,
    reason: "",
    status: "Pending",
    approver: employees.find((e) => e.designation?.includes("HR") || e.designation?.includes("Director") || e.name === "EMP-001")?.name || "",
  };

  const [formData, setFormData] = useState(initialForm);
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [balanceInfo, setBalanceInfo] = useState(null);
  const [loadingBalance, setLoadingBalance] = useState(false);

  useEffect(() => {
    async function checkBalance() {
      if (!isOpen || !formData.employee || !formData.leave_type) {
        setBalanceInfo(null);
        return;
      }
      setLoadingBalance(true);
      try {
        const bal = await apiGetLeaveBalance(formData.employee, formData.leave_type);
        setBalanceInfo(bal);
      } catch (err) {
        setBalanceInfo(null);
      } finally {
        setLoadingBalance(false);
      }
    }
    checkBalance();
  }, [isOpen, formData.employee, formData.leave_type]);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        employee: defaultEmpId,
        employee_name: defaultEmpName,
        leave_type: leaveTypes[0]?.leave_type_name || leaveTypes[0]?.name || "Annual Leave",
        from_date: new Date().toISOString().split("T")[0],
        to_date: new Date().toISOString().split("T")[0],
        total_days: 1,
        reason: "",
        status: "Pending",
        approver: employees.find((e) => e.designation?.includes("HR") || e.designation?.includes("Director") || e.name === "EMP-001")?.name || "",
      });
      setErrorMsg("");
      setSubmitting(false);
    }
  }, [isOpen, defaultEmpId, defaultEmpName, leaveTypes, employees]);

  const calculateDays = (start, end) => {
    if (!start || !end) return 1;
    const d1 = new Date(start);
    const d2 = new Date(end);
    if (d2 < d1) return 0;
    const diffTime = Math.abs(d2 - d1);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    return diffDays > 0 ? diffDays : 1;
  };

  const handleDateChange = (field, val) => {
    const from = field === "from_date" ? val : formData.from_date;
    const to = field === "to_date" ? val : formData.to_date;
    const days = calculateDays(from, to);

    setFormData({
      ...formData,
      [field]: val,
      total_days: days,
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.employee || !formData.leave_type) {
      setErrorMsg("Please select an employee and leave type.");
      return;
    }

    if (isAdmin) {
      const selectedEmp = employees.find((x) => (x.naming_series || x.name) === formData.employee);
      if (isAdminRecord(selectedEmp) || formData.employee === adminEmpId || formData.employee === "EMP-001") {
        setErrorMsg("Administrators are not permitted to apply for their own leave application.");
        return;
      }
    }

    if (new Date(formData.to_date) < new Date(formData.from_date)) {
      setErrorMsg("To Date cannot be earlier than From Date.");
      return;
    }

    try {
      setSubmitting(true);
      setErrorMsg("");
      if (onAddLeaveApplication) {
        await onAddLeaveApplication(formData);
      }
      onClose();
    } catch (err) {
      setErrorMsg(err.message || "Failed to submit leave application.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Apply for Leave"
      description="Fill out fields according to Leave Application DocType."
      maxWidth="max-w-lg"
    >
      <form onSubmit={handleSave} className="space-y-4 py-2">
        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-rose-600 dark:text-rose-400 text-xs flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {isAdmin && (
          <div className="p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/50 text-indigo-700 dark:text-indigo-300 text-xs flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-indigo-500" />
            <span>Administrators can apply for leave on behalf of staff members only.</span>
          </div>
        )}

        <div>
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Employee *</label>
          {canApprove ? (
            <Select
              value={formData.employee}
              onChange={(e) => {
                const emp = selectableEmployees.find((x) => (x.naming_series || x.name) === e.target.value);
                setFormData({
                  ...formData,
                  employee: e.target.value,
                  employee_name: emp ? emp.full_name : "",
                });
              }}
              required
            >
              <option value="">-- Select Employee --</option>
              {selectableEmployees.map((emp) => (
                <option key={emp.name || emp.naming_series} value={emp.name || emp.naming_series}>
                  {emp.full_name} ({emp.name || emp.naming_series})
                </option>
              ))}
            </Select>
          ) : (
            <Input
              value={`${defaultEmpName} (${defaultEmpId})`}
              disabled
              className="bg-slate-100 dark:bg-slate-800 text-slate-500 font-medium"
            />
          )}
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Leave Type *</label>
          <Select
            value={formData.leave_type}
            onChange={(e) => setFormData({ ...formData, leave_type: e.target.value })}
            required
          >
            {leaveTypes.map((lt, idx) => (
              <option key={lt.name || lt.leave_type_name || `lt-${idx}`} value={lt.leave_type_name || lt.name}>
                {lt.leave_type_name || lt.name} (Max {lt.max_days_per_year || 0} days/yr)
              </option>
            ))}
          </Select>

          {loadingBalance ? (
            <div className="mt-1.5 text-[11px] text-slate-400">Checking leave balance...</div>
          ) : balanceInfo ? (
            <div className="mt-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between text-xs gap-2">
              <span className="text-slate-600 dark:text-slate-400 font-medium flex items-center">
                <CalendarCheck className="h-3.5 w-3.5 mr-1 text-indigo-500" />
                <span>Balance:</span>
              </span>
              <div className="flex items-center space-x-2">
                <span className="text-slate-500">Allocated: <strong>{balanceInfo.allocated_days}</strong></span>
                <span className="text-amber-600 dark:text-amber-400">Used: <strong>{balanceInfo.used_days}</strong></span>
                <span
                  className={`font-bold px-2 py-0.5 rounded text-[11px] ${
                    balanceInfo.remaining_days < formData.total_days && balanceInfo.allocated_days > 0
                      ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                      : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  }`}
                >
                  Remaining: {balanceInfo.remaining_days} days
                </span>
              </div>
            </div>
          ) : null}

          {balanceInfo && balanceInfo.remaining_days < formData.total_days && balanceInfo.allocated_days > 0 && (
            <div className="mt-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/50 text-amber-700 dark:text-amber-300 text-[11px] flex items-center space-x-1.5">
              <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-500" />
              <span>Warning: Requested {formData.total_days} days exceeds remaining balance of {balanceInfo.remaining_days} days.</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">From Date *</label>
            <Input
              type="date"
              value={formData.from_date}
              onChange={(e) => handleDateChange("from_date", e.target.value)}
              required
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">To Date *</label>
            <Input
              type="date"
              value={formData.to_date}
              onChange={(e) => handleDateChange("to_date", e.target.value)}
              required
            />
          </div>
        </div>

        <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-lg border border-slate-200 dark:border-slate-700 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Calculated Total Days:</span>
          <span className="text-sm font-bold text-indigo-600 dark:text-indigo-400">{formData.total_days} Day(s)</span>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Reason</label>
          <Input
            placeholder="Reason for leave request..."
            value={formData.reason}
            onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
          />
        </div>

        {canApprove && (
          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Assigned Approver</label>
            <Select
              value={formData.approver}
              onChange={(e) => setFormData({ ...formData, approver: e.target.value })}
            >
              <option value="">-- Select Approver --</option>
              {employees.map((emp) => (
                <option key={emp.name || emp.naming_series} value={emp.name || emp.naming_series}>
                  {emp.full_name} ({emp.designation || emp.name})
                </option>
              ))}
            </Select>
          </div>
        )}

        <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-3">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting} className="bg-indigo-600 hover:bg-indigo-700 font-semibold cursor-pointer">
            {submitting ? "Submitting..." : "Submit Application"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
