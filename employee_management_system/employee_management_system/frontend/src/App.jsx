import { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { DashboardModule } from "./modules/DashboardModule";
import { EmployeeModule } from "./modules/EmployeeModule";
import { DepartmentModule } from "./modules/DepartmentModule";
import { AttendanceModule } from "./modules/AttendanceModule";
import { LeaveApplicationModule } from "./modules/LeaveApplicationModule";
import { LeaveTypeModule } from "./modules/LeaveTypeModule";
import { SalarySlipModule } from "./modules/SalarySlipModule";
import { PayrollModule } from "./modules/PayrollModule";
import { ChatModule } from "./modules/ChatModule";
import { ShiftManagementModule } from "./modules/ShiftManagementModule";
import { LoginModule } from "./modules/LoginModule";
import { Loader2 } from "lucide-react";

import {
  apiGetCurrentUser,
  apiLogout,
  apiFetchEmployees,
  apiCreateEmployee,
  apiUpdateEmployee,
  apiDeleteEmployee,
  apiFetchDepartments,
  apiCreateDepartment,
  apiUpdateDepartment,
  apiFetchAttendance,
  apiCreateAttendance,
  apiUpdateAttendance,
  apiDeleteAttendance,
  apiFetchLeaveApplications,
  apiCreateLeaveApplication,
  apiUpdateLeaveStatus,
  apiDeleteLeaveApplication,
  apiFetchLeaveTypes,
  apiCreateLeaveType,
  apiUpdateLeaveType,
  apiDeleteLeaveType,
  apiFetchSalarySlips,
  apiCreateSalarySlip,
  apiUpdateSalarySlip,
  apiDeleteSalarySlip,
  apiFetchPayrolls,
} from "./services/apiService";

import {
  INITIAL_EMPLOYEES,
  INITIAL_DEPARTMENTS,
  INITIAL_ATTENDANCE,
  INITIAL_LEAVE_APPLICATIONS,
  INITIAL_LEAVE_TYPES,
  INITIAL_SALARY_SLIPS,
  INITIAL_PAYROLLS,
} from "./services/mockData";

const ALL_KNOWN_TABS = [
  "dashboard",
  "employee",
  "department",
  "attendance",
  "shifts",
  "leave_application",
  "leave_type",
  "salary_slip",
  "payroll",
  "chat",
];

const getInitialTab = () => {
  try {
    if (typeof window !== "undefined") {
      const hash = window.location.hash.replace(/^#\/?/, "").trim();
      if (hash && ALL_KNOWN_TABS.includes(hash)) {
        return hash;
      }
      const saved = localStorage.getItem("ems_active_tab");
      if (saved && ALL_KNOWN_TABS.includes(saved)) {
        return saved;
      }
    }
  } catch (e) {
    console.warn("Error reading initial tab:", e);
  }
  return "dashboard";
};

export default function App() {
  // Auth state
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  // App navigation and search (persisted across page refresh)
  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [searchValue, setSearchValue] = useState("");
  const [loading, setLoading] = useState(false);

  // Master module records
  const [employees, setEmployees] = useState(INITIAL_EMPLOYEES);
  const [departments, setDepartments] = useState(INITIAL_DEPARTMENTS);
  const [attendance, setAttendance] = useState(INITIAL_ATTENDANCE);
  const [leaveApplications, setLeaveApplications] = useState(INITIAL_LEAVE_APPLICATIONS);
  const [leaveTypes, setLeaveTypes] = useState(INITIAL_LEAVE_TYPES);
  const [salarySlips, setSalarySlips] = useState(INITIAL_SALARY_SLIPS);
  const [payrolls, setPayrolls] = useState(INITIAL_PAYROLLS);
  const [autoOpenAddEmployee, setAutoOpenAddEmployee] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const userRole = currentUser?.role || null;
  const isValidRole = ["Administrator", "HR", "Employee"].includes(userRole);

  const ALLOWED_EMPLOYEE_TABS = [
    "dashboard",
    "employee",
    "leave_application",
    "salary_slip",
    "chat",
  ];
  const ALLOWED_HR_TABS = [
    "dashboard",
    "employee",
    "department",
    "attendance",
    "shifts",
    "leave_application",
    "leave_type",
    "salary_slip",
    "payroll",
    "chat",
  ];

  // Derive active tab safely based on role
  const isTabAllowed =
    userRole === "Administrator" ? true :
    userRole === "HR" ? ALLOWED_HR_TABS.includes(activeTab) :
    userRole === "Employee" ? ALLOWED_EMPLOYEE_TABS.includes(activeTab) :
    false;

  const currentTab = isTabAllowed ? activeTab : "dashboard";

  const handleSelectTab = (tab) => {
    if (userRole === "Employee" && !ALLOWED_EMPLOYEE_TABS.includes(tab)) {
      setActiveTab("dashboard");
      localStorage.setItem("ems_active_tab", "dashboard");
      window.location.hash = "dashboard";
      return;
    }
    if (userRole === "HR" && !ALLOWED_HR_TABS.includes(tab)) {
      setActiveTab("dashboard");
      localStorage.setItem("ems_active_tab", "dashboard");
      window.location.hash = "dashboard";
      return;
    }
    setActiveTab(tab);
    localStorage.setItem("ems_active_tab", tab);
    if (window.location.hash.replace(/^#\/?/, "").trim() !== tab) {
      window.location.hash = tab;
    }
  };

  // Listen for browser back / forward navigation via hashchange
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#\/?/, "").trim();
      if (hash && ALL_KNOWN_TABS.includes(hash) && hash !== activeTab) {
        handleSelectTab(hash);
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [activeTab, userRole]);

  // Synchronize state and hash when auth finishes loading
  useEffect(() => {
    if (!currentUser || authLoading) return;
    const role = currentUser.role;
    const allowed =
      role === "Administrator" ? true :
      role === "HR" ? ALLOWED_HR_TABS.includes(activeTab) :
      role === "Employee" ? ALLOWED_EMPLOYEE_TABS.includes(activeTab) :
      false;

    if (!allowed) {
      setActiveTab("dashboard");
      localStorage.setItem("ems_active_tab", "dashboard");
      window.location.hash = "dashboard";
    } else {
      localStorage.setItem("ems_active_tab", activeTab);
      if (window.location.hash.replace(/^#\/?/, "").trim() !== activeTab) {
        window.location.hash = activeTab;
      }
    }
  }, [currentUser, authLoading]);

  // Data loader for manual refresh
  const loadBackendData = useCallback(async () => {
    setLoading(true);
    try {
      const [
        empData,
        deptData,
        attData,
        leaveAppData,
        leaveTypeData,
        slipData,
        payrollData,
      ] = await Promise.all([
        apiFetchEmployees(),
        apiFetchDepartments(),
        apiFetchAttendance(),
        apiFetchLeaveApplications(),
        apiFetchLeaveTypes(),
        apiFetchSalarySlips(),
        apiFetchPayrolls(),
      ]);

      if (Array.isArray(empData)) setEmployees(empData);
      if (Array.isArray(deptData)) setDepartments(deptData);
      if (Array.isArray(attData)) setAttendance(attData);
      if (Array.isArray(leaveAppData)) setLeaveApplications(leaveAppData);
      if (Array.isArray(leaveTypeData)) setLeaveTypes(leaveTypeData);
      if (Array.isArray(slipData)) setSalarySlips(slipData);
      if (Array.isArray(payrollData)) setPayrolls(payrollData);
    } catch (err) {
      console.error("Failed loading Frappe backend data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial Auth Check
  useEffect(() => {
    let active = true;
    async function checkAuth() {
      setAuthLoading(true);
      try {
        const user = await apiGetCurrentUser();
        if (!active) return;
        if (user && user.is_logged_in && user.user !== "Guest") {
          setCurrentUser(user);
          setIsLoggedIn(true);
        } else {
          setCurrentUser(null);
          setIsLoggedIn(false);
        }
      } catch (e) {
        console.warn("Auth check error:", e);
        if (active) {
          setCurrentUser(null);
          setIsLoggedIn(false);
        }
      } finally {
        if (active) setAuthLoading(false);
      }
    }
    checkAuth();
    return () => {
      active = false;
    };
  }, []);

  // When auth state changes to logged in, load data safely
  useEffect(() => {
    if (!isLoggedIn) return;
    let isSubscribed = true;

    async function fetchData() {
      setLoading(true);
      try {
        const [
          empData,
          deptData,
          attData,
          leaveAppData,
          leaveTypeData,
          slipData,
          payrollData,
        ] = await Promise.all([
          apiFetchEmployees(),
          apiFetchDepartments(),
          apiFetchAttendance(),
          apiFetchLeaveApplications(),
          apiFetchLeaveTypes(),
          apiFetchSalarySlips(),
          apiFetchPayrolls(),
        ]);

        if (!isSubscribed) return;
        if (Array.isArray(empData)) setEmployees(empData);
        if (Array.isArray(deptData)) setDepartments(deptData);
        if (Array.isArray(attData)) setAttendance(attData);
        if (Array.isArray(leaveAppData)) setLeaveApplications(leaveAppData);
        if (Array.isArray(leaveTypeData)) setLeaveTypes(leaveTypeData);
        if (Array.isArray(slipData)) setSalarySlips(slipData);
        if (Array.isArray(payrollData)) setPayrolls(payrollData);
      } catch (err) {
        console.error("Failed loading Frappe backend data:", err);
      } finally {
        if (isSubscribed) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      isSubscribed = false;
    };
  }, [isLoggedIn]);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    setIsLoggedIn(true);
    const initial = getInitialTab();
    const role = user?.role;
    const allowed =
      role === "Administrator" ? true :
      role === "HR" ? ALLOWED_HR_TABS.includes(initial) :
      role === "Employee" ? ALLOWED_EMPLOYEE_TABS.includes(initial) :
      false;
    const target = allowed ? initial : "dashboard";
    setActiveTab(target);
    localStorage.setItem("ems_active_tab", target);
    window.location.hash = target;
  };

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (err) {
      console.warn("Logout error:", err);
    } finally {
      setCurrentUser(null);
      setIsLoggedIn(false);
      setActiveTab("dashboard");
      localStorage.removeItem("ems_active_tab");
      window.location.hash = "";
    }
  };

  // ---------------- Handlers for Employees ----------------
  const handleAddEmployee = async (newEmp) => {
    setEmployees((prev) => [newEmp, ...prev]);
    try {
      await apiCreateEmployee(newEmp);
      await loadBackendData();
    } catch (e) {
      console.error("Create employee error:", e);
      await loadBackendData();
    }
  };

  const handleUpdateEmployee = async (updated) => {
    const targetId = updated.name || updated.naming_series;
    setEmployees((prev) =>
      prev.map((e) => (e.naming_series === targetId || e.name === targetId ? updated : e))
    );
    try {
      await apiUpdateEmployee(targetId, updated);
      await loadBackendData();
    } catch (e) {
      console.error("Update employee error:", e);
      await loadBackendData();
    }
  };

  const handleDeleteEmployee = async (id) => {
    setEmployees((prev) => prev.filter((e) => e.naming_series !== id && e.name !== id));
    try {
      await apiDeleteEmployee(id);
      await loadBackendData();
    } catch (e) {
      console.error("Delete employee error:", e);
      await loadBackendData();
    }
  };

  // ---------------- Handlers for Departments ----------------
  const handleAddDepartment = async (newDept) => {
    setDepartments((prev) => [newDept, ...prev]);
    try {
      await apiCreateDepartment(newDept);
      await loadBackendData();
    } catch (e) {
      console.error("Create department error:", e);
      await loadBackendData();
    }
  };

  const handleUpdateDepartment = async (updated) => {
    const targetId = updated.original_name || updated.name || updated.department_name;
    setDepartments((prev) =>
      prev.map((d) =>
        d.name === targetId || d.department_name === targetId ? { ...d, ...updated } : d
      )
    );
    try {
      await apiUpdateDepartment(targetId, updated);
      await loadBackendData();
    } catch (e) {
      console.error("Update department error:", e);
      await loadBackendData();
    }
  };

  const handleDeleteDepartment = async (id) => {
    setDepartments((prev) => prev.filter((d) => d.name !== id && d.department_name !== id));
    try {
      await apiDeleteDepartment(id);
      await loadBackendData();
    } catch (e) {
      console.error("Delete department error:", e);
      await loadBackendData();
    }
  };

  // ---------------- Handlers for Attendance ----------------
  const handleAddAttendance = async (newAtt) => {
    setAttendance((prev) => [newAtt, ...prev]);
    try {
      await apiCreateAttendance(newAtt);
      await loadBackendData();
    } catch (e) {
      console.error("Create attendance error:", e);
      await loadBackendData();
    }
  };
  const handleUpdateAttendance = async (updated) => {
    setAttendance((prev) => prev.map((a) => (a.name === updated.name ? updated : a)));
    try {
      await apiUpdateAttendance(updated.name, updated);
      await loadBackendData();
    } catch (e) {
      console.error("Update attendance error:", e);
      await loadBackendData();
    }
  };
  const handleDeleteAttendance = async (id) => {
    setAttendance((prev) => prev.filter((a) => a.name !== id));
    try {
      await apiDeleteAttendance(id);
      await loadBackendData();
    } catch (e) {
      console.error("Delete attendance error:", e);
      await loadBackendData();
    }
  };

  // ---------------- Handlers for Leave Applications ----------------
  const handleAddLeaveApplication = async (newApp) => {
    try {
      const created = await apiCreateLeaveApplication(newApp);
      if (created && created.name) {
        setLeaveApplications((prev) => [created, ...prev.filter((l) => l.name !== created.name)]);
      }
      await loadBackendData();
    } catch (e) {
      console.error("Create leave application error:", e);
      await loadBackendData();
      throw e;
    }
  };

  const handleUpdateLeaveStatus = async (id, newStatus) => {
    setLeaveApplications((prev) =>
      prev.map((l) => (l.name === id ? { ...l, status: newStatus } : l))
    );
    try {
      await apiUpdateLeaveStatus(id, newStatus);
      await loadBackendData();
    } catch (e) {
      console.error("Update leave status error:", e);
      await loadBackendData();
      throw e;
    }
  };

  const handleDeleteLeaveApplication = async (id) => {
    setLeaveApplications((prev) => prev.filter((l) => l.name !== id));
    try {
      await apiDeleteLeaveApplication(id);
      await loadBackendData();
    } catch (e) {
      console.error("Delete leave application error:", e);
      await loadBackendData();
      throw e;
    }
  };

  // ---------------- Handlers for Leave Types ----------------
  const handleAddLeaveType = async (newLt) => {
    try {
      const created = await apiCreateLeaveType(newLt);
      if (created && (created.name || created.leave_type_name)) {
        setLeaveTypes((prev) => [created, ...prev.filter((l) => l.name !== (created.name || created.leave_type_name))]);
      }
      await loadBackendData();
    } catch (e) {
      console.error("Create leave type error:", e);
      await loadBackendData();
      throw e;
    }
  };

  const handleUpdateLeaveType = async (name, updated) => {
    setLeaveTypes((prev) =>
      prev.map((lt) => (lt.name === name || lt.leave_type_name === name ? { ...lt, ...updated } : lt))
    );
    try {
      await apiUpdateLeaveType(name, updated);
      await loadBackendData();
    } catch (e) {
      console.error("Update leave type error:", e);
      await loadBackendData();
      throw e;
    }
  };

  const handleDeleteLeaveType = async (id) => {
    setLeaveTypes((prev) => prev.filter((lt) => lt.name !== id && lt.leave_type_name !== id));
    try {
      await apiDeleteLeaveType(id);
      await loadBackendData();
    } catch (e) {
      console.error("Delete leave type error:", e);
      await loadBackendData();
      throw e;
    }
  };

  // ---------------- Handlers for Salary Slips ----------------
  const handleAddSalarySlip = async (newSlip) => {
    setSalarySlips((prev) => [newSlip, ...prev]);
    try {
      await apiCreateSalarySlip(newSlip);
      await loadBackendData();
    } catch (e) {
      console.error("Create salary slip error:", e);
      await loadBackendData();
    }
  };

  const handleUpdateSalarySlip = async (updated) => {
    const targetId = updated.name;
    setSalarySlips((prev) =>
      prev.map((s) => (s.name === targetId ? { ...s, ...updated } : s))
    );
    try {
      await apiUpdateSalarySlip(targetId, updated);
      await loadBackendData();
    } catch (e) {
      console.error("Update salary slip error:", e);
      await loadBackendData();
    }
  };

  const handleDeleteSalarySlip = async (id) => {
    setSalarySlips((prev) => prev.filter((s) => s.name !== id));
    try {
      await apiDeleteSalarySlip(id);
      await loadBackendData();
    } catch (e) {
      console.error("Delete salary slip error:", e);
      await loadBackendData();
    }
  };

  // ---------------- Handlers for Payroll ----------------
  const handleAddPayroll = (newPr) => setPayrolls((prev) => [newPr, ...prev]);
  const handleUpdatePayroll = (updated) =>
    setPayrolls((prev) => prev.map((p) => (p.name === updated.name ? updated : p)));
  const handleDeletePayroll = (id) =>
    setPayrolls((prev) => prev.filter((p) => p.name !== id));

  // Module Title Helper
  const getTabTitle = () => {
    switch (currentTab) {
      case "dashboard":
        return "Dashboard";
      case "employee":
        return userRole === "Employee" ? "My Profile" : "Employee Directory";
      case "department":
        return "Departments";
      case "attendance":
        return "Attendance";
      case "shifts":
        return "Shift & Holiday Management";
      case "leave_application":
        return userRole === "Employee" ? "My Leaves" : "Leave Applications";
      case "leave_type":
        return "Leave Policies";
      case "salary_slip":
        return userRole === "Employee" ? "My Paystubs" : "Salary Slips";
      case "payroll":
        return "Payroll Runs";
      case "chat":
        return "SQL Assistant";
      default:
        return "Employee Management System";
    }
  };

  const counts = {
    employees: employees.length,
    departments: departments.length,
    attendance: attendance.length,
    leaves: leaveApplications.filter((l) => l.status === "Pending").length,
    slips: salarySlips.length,
  };

  // Render Loading Screen
  if (authLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
            Checking session...
          </p>
        </div>
      </div>
    );
  }

  // Render Login Module if unauthenticated
  if (!isLoggedIn) {
    return <LoginModule onLoginSuccess={handleLoginSuccess} />;
  }

  // Render Unauthorized screen if role is unrecognized
  if (!isValidRole) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
        <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-8 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center mb-4">
            <span className="text-rose-600 dark:text-rose-400 font-bold text-xl">!</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Access Restricted</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
            Your account ({currentUser?.email || currentUser?.user}) does not have an authorized role assigned (Administrator, HR, or Employee). Please contact your system administrator.
          </p>
          <button
            onClick={handleLogout}
            className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm transition-colors shadow-sm"
          >
            Sign Out
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full bg-slate-50/50 dark:bg-slate-950 theme-blue:bg-[#0a1128] overflow-hidden font-sans text-slate-900 dark:text-slate-100 theme-blue:text-blue-50 transition-colors duration-200">
      {/* Collapsible Sidebar */}
      <Sidebar
        activeTab={currentTab}
        setActiveTab={handleSelectTab}
        counts={counts}
        currentUser={currentUser}
        onLogout={handleLogout}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Main Layout Area */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <Header
          activeTabName={getTabTitle()}
          searchValue={searchValue}
          onSearchChange={setSearchValue}
          onRefresh={loadBackendData}
          currentUser={currentUser}
          onLogout={handleLogout}
          onToggleMobileSidebar={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          onNavigate={handleSelectTab}
        />

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">
            {loading && (
              <div className="mb-4 flex items-center space-x-2 text-xs text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-3 py-1.5 rounded-lg border border-indigo-100 dark:border-indigo-900/60 w-fit">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Syncing live records with Frappe backend...</span>
              </div>
            )}

            {currentTab === "dashboard" && (
              <DashboardModule
                employees={employees}
                departments={departments}
                attendance={attendance}
                leaveApplications={leaveApplications}
                leaveTypes={leaveTypes}
                salarySlips={salarySlips}
                setActiveTab={handleSelectTab}
                onUpdateLeaveStatus={handleUpdateLeaveStatus}
                onAddEmployee={handleAddEmployee}
                onAddLeaveApplication={handleAddLeaveApplication}
                userRole={userRole}
                currentUser={currentUser}
              />
            )}

            {currentTab === "employee" && (
              <EmployeeModule
                employees={employees}
                departments={departments}
                userRole={userRole}
                currentUser={currentUser}
                onAddEmployee={handleAddEmployee}
                onUpdateEmployee={handleUpdateEmployee}
                onDeleteEmployee={handleDeleteEmployee}
                searchQuery={searchValue}
                autoOpenAdd={autoOpenAddEmployee}
                onResetAutoOpenAdd={() => setAutoOpenAddEmployee(false)}
              />
            )}

            {currentTab === "department" && (
              <DepartmentModule
                departments={departments}
                employees={employees}
                userRole={userRole}
                onAddDepartment={handleAddDepartment}
                onUpdateDepartment={handleUpdateDepartment}
                onDeleteDepartment={handleDeleteDepartment}
              />
            )}

            {currentTab === "attendance" && (
              <AttendanceModule
                attendance={attendance}
                employees={employees}
                leaveApplications={leaveApplications}
                userRole={userRole}
                currentUser={currentUser}
                onRefreshData={loadBackendData}
                onAddAttendance={handleAddAttendance}
                onUpdateAttendance={handleUpdateAttendance}
                onDeleteAttendance={handleDeleteAttendance}
              />
            )}

            {currentTab === "shifts" && (
              <ShiftManagementModule
                employees={employees}
                userRole={userRole}
              />
            )}

            {currentTab === "leave_application" && (
              <LeaveApplicationModule
                leaveApplications={leaveApplications}
                leaveTypes={leaveTypes}
                employees={employees}
                userRole={userRole}
                currentUser={currentUser}
                onAddLeaveApplication={handleAddLeaveApplication}
                onUpdateLeaveStatus={handleUpdateLeaveStatus}
                onDeleteLeaveApplication={handleDeleteLeaveApplication}
                onRefreshData={loadBackendData}
              />
            )}

            {currentTab === "leave_type" && (
              <LeaveTypeModule
                leaveTypes={leaveTypes}
                userRole={userRole}
                onAddLeaveType={handleAddLeaveType}
                onUpdateLeaveType={handleUpdateLeaveType}
                onDeleteLeaveType={handleDeleteLeaveType}
              />
            )}

            {currentTab === "salary_slip" && (
              <SalarySlipModule
                salarySlips={salarySlips}
                employees={employees}
                userRole={userRole}
                onAddSalarySlip={handleAddSalarySlip}
                onUpdateSalarySlip={handleUpdateSalarySlip}
                onDeleteSalarySlip={handleDeleteSalarySlip}
                onRefreshData={loadBackendData}
              />
            )}

            {currentTab === "payroll" && (
              <PayrollModule
                payrolls={payrolls}
                departments={departments}
                employees={employees}
                onAddPayroll={handleAddPayroll}
                onUpdatePayroll={handleUpdatePayroll}
                onDeletePayroll={handleDeletePayroll}
                onRefreshData={loadBackendData}
              />
            )}

            {currentTab === "chat" && <ChatModule currentUser={currentUser} />}
          </div>
        </main>
      </div>
    </div>
  );
}