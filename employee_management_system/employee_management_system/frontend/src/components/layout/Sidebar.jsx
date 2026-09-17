import { useState } from "react";
import {
  LayoutDashboard,
  Users,
  Building2,
  FileSpreadsheet,
  CalendarOff,
  CalendarCheck,
  Receipt,
  CreditCard,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  X,
  Clock,
} from "lucide-react";
import { Badge } from "../ui/badge";

const ALL_NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, badge: "Overview", roles: ["Administrator", "HR", "Employee"] },
  { id: "employee", label: "Employees", icon: Users, countKey: "employees", roles: ["Administrator", "HR"] },
  { id: "employee", label: "My Profile", icon: Users, roles: ["Employee"] },
  { id: "department", label: "Departments", icon: Building2, countKey: "departments", roles: ["Administrator", "HR"] },
  { id: "attendance", label: "Attendance", icon: CalendarCheck, countKey: "attendance", roles: ["Administrator", "HR"] },
  { id: "shifts", label: "Shifts & Holidays", icon: Clock, roles: ["Administrator", "HR"] },
  { id: "leave_application", label: "Leave Requests", icon: FileSpreadsheet, countKey: "leaves", roles: ["Administrator", "HR"] },
  { id: "leave_application", label: "My Leaves", icon: FileSpreadsheet, countKey: "leaves", roles: ["Employee"] },
  { id: "leave_type", label: "Leave Policies", icon: CalendarOff, roles: ["Administrator", "HR"] },
  { id: "salary_slip", label: "Salary Slips", icon: Receipt, countKey: "slips", roles: ["Administrator", "HR"] },
  { id: "salary_slip", label: "My Paystubs", icon: Receipt, roles: ["Employee"] },
  { id: "payroll", label: "Payroll Processing", icon: CreditCard, roles: ["Administrator", "HR"] },
  { id: "chat", label: "SQL Assistant", icon: MessageSquare, badge: "AI", roles: ["Administrator", "HR", "Employee"] },
];



export function Sidebar({
  activeTab,
  setActiveTab,
  counts = {},
  currentUser = {},
  mobileOpen = false,
  onCloseMobile,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const role = currentUser.role || "Employee";

  // Filter items matching user role
  const visibleNavItems = ALL_NAV_ITEMS.filter((item) => item.roles.includes(role));

  // Determine initials
  const initials = (currentUser.full_name || currentUser.user || "User")
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleNavClick = (tabId) => {
    // Strictly verify role permission before switching tabs
    const targetItem = visibleNavItems.find((i) => i.id === tabId);
    if (!targetItem) return;

    setActiveTab(tabId);
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs md:hidden animate-in fade-in duration-200"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed md:relative inset-y-0 left-0 z-50 md:z-auto flex flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 theme-blue:border-[#1c2d58] theme-blue:bg-[#111c3a] transition-all duration-300 ease-in-out shadow-xs select-none ${
          mobileOpen ? "translate-x-0 w-64 shadow-2xl" : "-translate-x-full md:translate-x-0"
        } ${collapsed ? "md:w-20" : "md:w-64"}`}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58]">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 theme-blue:from-blue-600 theme-blue:to-cyan-500 text-white shadow-md shadow-indigo-200 dark:shadow-indigo-950 theme-blue:shadow-blue-950">
              <Sparkles className="h-5 w-5" />
            </div>
            {(!collapsed || mobileOpen) && (
              <div className="flex flex-col overflow-hidden">
                <span className="text-base font-bold text-slate-900 dark:text-slate-100 theme-blue:text-blue-50 truncate tracking-tight">
                  EmpManager
                </span>
                <span className="text-[11px] font-medium text-slate-400 dark:text-slate-500 theme-blue:text-blue-400 truncate tracking-wider uppercase">
                  {role} Workspace
                </span>
              </div>
            )}
          </div>

          {/* Mobile Close Button */}
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="md:hidden flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              title="Close navigation"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Navigation Section */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {(!collapsed || mobileOpen) && (
            <div className="px-3 pb-2 text-[11px] font-semibold text-slate-400 dark:text-slate-500 theme-blue:text-blue-400 uppercase tracking-wider flex items-center justify-between">
              {/* <span>Navigation</span>
              <span className="text-[10px] font-normal text-indigo-500 lowercase">{role}</span> */}
            </div>
          )}

          {visibleNavItems.map((item, idx) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            const count = item.countKey ? counts[item.countKey] : null;

            return (
              <button
                key={`${item.id}-${idx}`}
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all group cursor-pointer ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 theme-blue:bg-blue-900/60 theme-blue:text-blue-200 shadow-xs font-semibold"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/70 dark:hover:text-slate-100 theme-blue:text-blue-300 theme-blue:hover:bg-[#18274d] theme-blue:hover:text-blue-100"
                }`}
                title={collapsed && !mobileOpen ? item.label : undefined}
              >
              <div className="flex items-center space-x-3 overflow-hidden">
                <Icon
                  className={`h-5 w-5 shrink-0 transition-transform group-hover:scale-105 ${
                    isActive
                      ? "text-indigo-600 dark:text-indigo-400 theme-blue:text-blue-400"
                      : "text-slate-400 dark:text-slate-500 theme-blue:text-blue-400/70 group-hover:text-slate-600 dark:group-hover:text-slate-300 theme-blue:group-hover:text-blue-200"
                  }`}
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </div>

              {!collapsed && (
                <div className="flex items-center space-x-1.5">
                  {item.badge && (
                    <Badge variant="default" className="text-[10px] px-1.5 py-0 bg-indigo-600 text-white">
                      {item.badge}
                    </Badge>
                  )}
                  {count !== undefined && count !== null && count > 0 && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        isActive
                          ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/80 dark:text-indigo-200 theme-blue:bg-blue-800/80 theme-blue:text-blue-100"
                          : "bg-slate-100 text-slate-500 group-hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:group-hover:bg-slate-700 theme-blue:bg-[#18274d] theme-blue:text-blue-300"
                      }`}
                    >
                      {count}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer Profile */}
      <div className="relative border-t border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58] p-3">
        {/* Floating Border Edge Collapse Button (down in sidebar, up of employee details div) */}
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="hidden md:flex absolute -right-3 -top-3 z-40 h-6 w-6 items-center justify-center rounded-full bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-700 theme-blue:border-[#1c2d58] text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-white theme-blue:text-blue-300 theme-blue:hover:text-white shadow-xs hover:shadow-md transition-all hover:scale-110 cursor-pointer"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>

        <div
          className={`flex items-center rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#18274d] p-2.5 ${
            collapsed ? "justify-center" : "justify-between"
          }`}
        >
          <div className="flex items-center space-x-2.5 overflow-hidden">
            <div className="relative shrink-0">
              <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 theme-blue:from-blue-500 theme-blue:to-cyan-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
                {initials}
              </div>
              <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-slate-900 theme-blue:ring-[#111c3a]" />
            </div>

            {!collapsed && (
              <div className="flex flex-col overflow-hidden min-w-0">
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-blue-100 truncate">
                  {currentUser.full_name || currentUser.user || "User"}
                </span>
                {(currentUser.email || currentUser.employee?.email || (currentUser.user && currentUser.user.includes("@") ? currentUser.user : null)) && (
                  <span className="text-[10px] text-slate-400 dark:text-slate-500 theme-blue:text-blue-400/90 truncate font-mono">
                    {currentUser.email || currentUser.employee?.email || currentUser.user}
                  </span>
                )}
              </div>
            )}
          </div>

      
        </div>
      </div>
    </aside>
    </>
  );
}
