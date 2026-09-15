import { useState, useEffect, useRef } from "react";
import {
  Search,
  RefreshCw,
  Sun,
  Moon,
  Droplets,
  LogOut,
  Menu,
  Bell,
  CheckCheck,
  Check,
  Info,
  Trash2,
  X,
} from "lucide-react";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import {
  apiFetchNotifications,
  apiMarkNotificationRead,
  apiMarkAllNotificationsRead,
  apiClearNotifications,
} from "../../services/apiService";

export function Header({
  activeTabName,
  onSearchChange,
  searchValue,
  onRefresh,
  currentUser = {},
  onLogout,
  onToggleMobileSidebar,
  onNavigate,
}) {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("app_theme") || "light";
  });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [avatarDropdownOpen, setAvatarDropdownOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const avatarDropdownRef = useRef(null);
  const notificationDropdownRef = useRef(null);

  // Load notifications
  const loadNotifications = async () => {
    try {
      const res = await apiFetchNotifications(25);
      if (res && Array.isArray(res.notifications)) {
        setNotifications(res.notifications);
        setUnreadCount(res.unread_count || 0);
      }
    } catch (err) {
      console.error("Failed to load notifications:", err);
    }
  };

  useEffect(() => {
    if (currentUser?.is_logged_in !== false) {
      loadNotifications();
      const interval = setInterval(loadNotifications, 30000); // 30s poll
      return () => clearInterval(interval);
    }
  }, [currentUser]);

  // Close avatar and notification dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (avatarDropdownOpen && avatarDropdownRef.current && !avatarDropdownRef.current.contains(e.target)) {
        setAvatarDropdownOpen(false);
      }
      if (notificationsOpen && notificationDropdownRef.current && !notificationDropdownRef.current.contains(e.target)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [avatarDropdownOpen, notificationsOpen]);

  const handleMarkNotificationRead = async (name) => {
    try {
      await apiMarkNotificationRead(name);
      setNotifications((prev) =>
        prev.map((n) => (n.name === name ? { ...n, read: 1 } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error("Failed to mark notification read:", err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await apiMarkAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: 1 })));
      setUnreadCount(0);
    } catch (err) {
      console.error("Failed to mark all notifications read:", err);
    }
  };

  const handleClearAllNotifications = async () => {
    try {
      await apiClearNotifications("all");
      setNotifications([]);
      setUnreadCount(0);
    } catch (err) {
      console.error("Failed to clear all notifications:", err);
    }
  };

  const handleClearNotification = async (name) => {
    try {
      await apiClearNotifications(name);
      setNotifications((prev) => {
        const target = prev.find((n) => n.name === name);
        if (target && !target.read) {
          setUnreadCount((c) => Math.max(0, c - 1));
        }
        return prev.filter((n) => n.name !== name);
      });
    } catch (err) {
      console.error("Failed to clear notification:", err);
    }
  };

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    const root = document.documentElement;

    if (theme === "dark") {
      root.classList.add("dark");
      root.classList.remove("theme-blue");
    } else if (theme === "blue") {
      root.classList.add("dark", "theme-blue");
    } else {
      root.classList.remove("dark", "theme-blue");
    }
    localStorage.setItem("app_theme", theme);
  }, [theme]);

  const handleNextTheme = () => {
    setTheme(theme === "dark" ? "blue" : theme === "blue" ? "light" : "dark");
  };

  const handleRefreshClick = async () => {
    if (!onRefresh || isRefreshing) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  const role = currentUser.role || "Employee";
  const initials = (currentUser.full_name || currentUser.user || "User")
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-4 sm:px-6 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95 theme-blue:border-[#1c2d58] theme-blue:bg-[#111c3a]/95 transition-colors">
      {/* Active Module Title, Hamburger on Mobile & Role Badge */}
      <div className="flex items-center space-x-2.5 sm:space-x-3 overflow-hidden">
        {onToggleMobileSidebar && (
          <button
            type="button"
            onClick={onToggleMobileSidebar}
            className="md:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer shrink-0"
            title="Toggle Navigation Menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <h1 className="text-base sm:text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 theme-blue:text-blue-50 capitalize truncate">
          {activeTabName}
        </h1>
        {/* <Badge
          variant={role === "Administrator" ? "default" : role === "HR" ? "success" : "secondary"}
          className="hidden sm:inline-flex text-[11px] font-medium shrink-0"
        >
          {role} View
        </Badge> */}
      </div>

      {/* Center Search & Actions */}
      <div className="flex items-center space-x-2 sm:space-x-3">
        <div className="relative w-32 xs:w-44 sm:w-64 md:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 theme-blue:text-blue-400" />
          <Input
            placeholder={`Search ${activeTabName}...`}
            className="pl-9 pr-3 bg-slate-50 border-slate-200 text-xs sm:text-sm focus:bg-white dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 theme-blue:bg-[#18274d] theme-blue:border-[#24396b] theme-blue:text-blue-100 transition-colors"
            value={searchValue || ""}
            onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
          />
        </div>

        {onRefresh && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefreshClick}
            title="Refresh Data"
            className="text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-indigo-400 cursor-pointer"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin text-indigo-600" : ""}`} />
          </Button>
        )}

        {/* Theme Toggle Icon Button (dark -> blue -> light) */}
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNextTheme}
          title={`Switch theme (Current: ${
            theme === "dark" ? "Dark" : theme === "blue" ? "Blue" : "Light"
          })`}
          className="text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-indigo-400 cursor-pointer"
        >
          {theme === "dark" ? (
            <Moon className="h-4 w-4 text-indigo-400" />
          ) : theme === "blue" ? (
            <Droplets className="h-4 w-4 text-blue-500" />
          ) : (
            <Sun className="h-4 w-4 text-amber-500" />
          )}
        </Button>

        {/* Notification Bell Dropdown */}
        <div className="relative shrink-0" ref={notificationDropdownRef}>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setNotificationsOpen(!notificationsOpen);
              if (!notificationsOpen) loadNotifications();
            }}
            title="Notifications"
            className="relative text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-indigo-400 cursor-pointer"
            aria-expanded={notificationsOpen}
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-xs animate-pulse">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </Button>

          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl dark:border-slate-800 dark:bg-slate-900 theme-blue:border-[#24396b] theme-blue:bg-[#111c3a] z-50 animate-in fade-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 mb-2 dark:border-slate-800 theme-blue:border-[#1c2d58]">
                <div className="flex items-center space-x-2">
                  <span className="font-semibold text-xs sm:text-sm text-slate-800 dark:text-slate-200 theme-blue:text-blue-50">
                    Notifications
                  </span>
                  {unreadCount > 0 && (
                    <span className="rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 px-1.5 py-0.5 text-[10px] font-bold">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-2.5">
                  {unreadCount > 0 && (
                    <button
                      type="button"
                      onClick={handleMarkAllRead}
                      className="flex items-center space-x-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 cursor-pointer"
                      title="Mark all notifications as read"
                    >
                      <CheckCheck className="h-3 w-3" />
                      <span>Mark read</span>
                    </button>
                  )}
                  {notifications.length > 0 && (
                    <button
                      type="button"
                      onClick={handleClearAllNotifications}
                      className="flex items-center space-x-1 text-[11px] font-medium text-rose-600 hover:text-rose-700 dark:text-rose-400 cursor-pointer"
                      title="Clear all notifications"
                    >
                      <Trash2 className="h-3 w-3" />
                      <span>Clear all</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1 text-xs">
                {notifications.length === 0 ? (
                  <div className="py-8 text-center text-slate-400 dark:text-slate-500">
                    <Info className="mx-auto h-6 w-6 mb-1 opacity-50" />
                    <p>No notifications yet</p>
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.name}
                      onClick={() => !n.read && handleMarkNotificationRead(n.name)}
                      className={`group relative p-2.5 rounded-xl border transition-all cursor-pointer ${
                        !n.read
                          ? "bg-indigo-50/70 border-indigo-100 dark:bg-indigo-950/30 dark:border-indigo-900/50 theme-blue:bg-blue-950/40 theme-blue:border-blue-900/60"
                          : "bg-transparent border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50 theme-blue:hover:bg-[#18274d]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-blue-100 text-[12px] leading-tight">
                          {n.subject}
                        </div>
                        <div className="flex items-center space-x-1.5 shrink-0">
                          {!n.read && (
                            <span className="h-2 w-2 rounded-full bg-indigo-600 shrink-0 mt-0.5" />
                          )}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleClearNotification(n.name);
                            }}
                            className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 p-0.5 rounded transition-opacity cursor-pointer"
                            title="Dismiss notification"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                      {n.email_content && (
                        <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed">
                          {n.email_content.replace(/<[^>]*>?/gm, "")}
                        </p>
                      )}
                      <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400 dark:text-slate-500">
                        <span>{n.creation ? new Date(n.creation).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}</span>
                        {n.document_type && (
                          <span className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-[9px] uppercase tracking-wider font-semibold">
                            {n.document_type}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Avatar Dropdown (Avatar only, Logout only) */}
        <div className="relative shrink-0" ref={avatarDropdownRef}>
          <button
            type="button"
            onClick={() => setAvatarDropdownOpen(!avatarDropdownOpen)}
            className="flex items-center justify-center p-0.5 rounded-full border border-slate-200 bg-slate-50 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 theme-blue:border-[#24396b] theme-blue:bg-[#18274d] transition-all cursor-pointer focus:outline-hidden"
            title={currentUser.full_name || currentUser.user || "User"}
            aria-expanded={avatarDropdownOpen}
          >
            <div className="relative">
              <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 theme-blue:from-blue-500 theme-blue:to-cyan-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
                {initials}
              </div>
              <span className="absolute bottom-0 right-0 h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-slate-900 theme-blue:ring-[#111c3a]" />
            </div>
          </button>

          {avatarDropdownOpen && (
            <div className="absolute right-0 mt-2 w-36 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-800 dark:bg-slate-900 theme-blue:border-[#24396b] theme-blue:bg-[#111c3a] z-50 animate-in fade-in zoom-in-95 duration-150">
              {onLogout && (
                <button
                  type="button"
                  onClick={() => {
                    setAvatarDropdownOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center space-x-2 px-2.5 py-2 rounded-lg text-xs font-medium text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 theme-blue:text-rose-400 theme-blue:hover:bg-rose-950/30 transition-colors cursor-pointer"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Logout</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
