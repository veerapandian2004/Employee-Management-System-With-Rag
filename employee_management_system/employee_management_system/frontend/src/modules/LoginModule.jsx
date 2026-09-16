import { useState, useEffect } from "react";
import {
  Sparkles,
  Lock,
  Mail,
  AlertCircle,
  ArrowRight,
  Shield,
  UserCheck,
  Users,
  Eye,
  EyeOff,
  Sun,
  Moon,
  Droplets,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { apiLogin, apiGetCurrentUser } from "../services/apiService";

export function LoginModule({ onLoginSuccess }) {
  const [usr, setUsr] = useState("");
  const [pwd, setPwd] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("app_theme") || "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
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

  const handleLogin = async (e, usernameOverride, passwordOverride) => {
    if (e) e.preventDefault();
    const finalUsr = (usernameOverride || usr).trim();
    let finalPwd = passwordOverride || pwd;

    if (!finalUsr || !finalPwd) {
      setError("Please enter your email/username and password.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      try {
        await apiLogin(finalUsr, finalPwd);
      } catch (loginErr) {
        // If password contained spaces, automatically retry with spaces stripped
        if (finalPwd.includes(" ")) {
          const noSpacePwd = finalPwd.replace(/\s+/g, "");
          await apiLogin(finalUsr, noSpacePwd);
          finalPwd = noSpacePwd;
          setPwd(noSpacePwd);
        } else {
          throw loginErr;
        }
      }
      const user = await apiGetCurrentUser();
      if (user && user.is_logged_in && user.user !== "Guest") {
        onLoginSuccess(user);
      } else {
        throw new Error("Invalid username or password. Please verify your credentials.");
      }
    } catch (err) {
      setError(err.message || "Invalid credentials. Please check and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (email, password) => {
    setUsr(email);
    setPwd(password);
    handleLogin(null, email, password);
  };

  return (
    <div className="min-h-screen relative flex flex-col justify-center items-center bg-gradient-to-br from-slate-100 via-indigo-50/50 to-slate-200 dark:from-slate-950 dark:via-indigo-950 dark:to-slate-900 theme-blue:from-[#060c1d] theme-blue:via-[#0a1128] theme-blue:to-[#0d1b3e] p-4 sm:p-6 text-slate-800 dark:text-slate-100 theme-blue:text-blue-50 transition-colors duration-200">
      {/* Top-Right Theme Switcher */}
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6">
        <button
          type="button"
          onClick={handleNextTheme}
          title={`Switch theme (Current: ${
            theme === "dark" ? "Dark" : theme === "blue" ? "Blue" : "Light"
          })`}
          className="flex items-center space-x-1.5 px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-slate-600 shadow-xs hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300 dark:hover:bg-slate-800 theme-blue:border-[#1c2d58] theme-blue:bg-[#111c3a]/90 theme-blue:text-blue-200 theme-blue:hover:bg-[#18274d] transition-all cursor-pointer backdrop-blur-md"
        >
          {theme === "dark" ? (
            <>
              <Moon className="h-4 w-4 text-indigo-400" />
              <span className="text-xs font-medium text-slate-300 hidden sm:inline">Dark</span>
            </>
          ) : theme === "blue" ? (
            <>
              <Droplets className="h-4 w-4 text-blue-400" />
              <span className="text-xs font-medium text-blue-200 hidden sm:inline">Blue</span>
            </>
          ) : (
            <>
              <Sun className="h-4 w-4 text-amber-500" />
              <span className="text-xs font-medium text-slate-700 hidden sm:inline">Light</span>
            </>
          )}
        </button>
      </div>

      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500 to-cyan-400 theme-blue:from-blue-600 theme-blue:to-cyan-400 text-white shadow-xl shadow-indigo-500/20 theme-blue:shadow-blue-500/20 mb-2">
            <Sparkles className="h-7 w-7" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white theme-blue:text-blue-50">
            Employee Management System
          </h1>
          <p className="text-sm text-slate-600 dark:text-indigo-200/80 theme-blue:text-blue-200/80">
            Sign in to access your dashboard, leaves, records, and HR workspace
          </p>
        </div>

        {/* Login Form Card */}
        <Card className="bg-white/95 border-slate-200 shadow-xl shadow-slate-200/60 dark:bg-slate-900/90 dark:border-slate-800 dark:shadow-2xl dark:shadow-slate-950/50 theme-blue:bg-[#111c3a]/90 theme-blue:border-[#1c2d58] theme-blue:shadow-2xl theme-blue:shadow-blue-950/60 backdrop-blur-xl transition-colors">
          <CardContent className="p-6 sm:p-8 space-y-5">
            {error && (
              <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-500 dark:text-rose-400 text-xs flex items-center space-x-2.5 animate-in fade-in duration-200">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 theme-blue:text-blue-200 block">
                  Email / Username
                </label>
                <div className="relative group">
                  <Mail className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400 group-focus-within:text-indigo-600 dark:text-slate-400 dark:group-focus-within:text-indigo-400 theme-blue:text-blue-400 theme-blue:group-focus-within:text-cyan-400 transition-colors pointer-events-none" />
                  <Input
                    type="text"
                    placeholder="admin@ems.com"
                    value={usr}
                    onChange={(e) => setUsr(e.target.value)}
                    className="pl-10 bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-indigo-600 focus:text-slate-900 dark:bg-slate-800/90 dark:border-slate-700 dark:text-white dark:placeholder:text-slate-500 dark:focus:bg-slate-800 dark:focus:border-indigo-500 dark:focus:text-white theme-blue:bg-[#18274d] theme-blue:border-[#24396b] theme-blue:text-blue-50 theme-blue:placeholder:text-blue-400/70 theme-blue:focus:bg-[#18274d] theme-blue:focus:border-blue-400 theme-blue:focus:text-blue-50 text-sm"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 theme-blue:text-blue-200 block">
                    Password
                  </label>
                  <span className="text-[10px] text-indigo-600 dark:text-indigo-300/80 theme-blue:text-blue-300/80 font-normal">
                    Full name without space (e.g. SarahJenkins)
                  </span>
                </div>
                <div className="relative group">
                  <Lock className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400 group-focus-within:text-indigo-600 dark:text-slate-400 dark:group-focus-within:text-indigo-400 theme-blue:text-blue-400 theme-blue:group-focus-within:text-cyan-400 transition-colors pointer-events-none" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="e.g. SarahJenkins"
                    value={pwd}
                    onChange={(e) => setPwd(e.target.value)}
                    className="pl-10 pr-10 bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-indigo-600 focus:text-slate-900 dark:bg-slate-800/90 dark:border-slate-700 dark:text-white dark:placeholder:text-slate-500 dark:focus:bg-slate-800 dark:focus:border-indigo-500 dark:focus:text-white theme-blue:bg-[#18274d] theme-blue:border-[#24396b] theme-blue:text-blue-50 theme-blue:placeholder:text-blue-400/70 theme-blue:focus:bg-[#18274d] theme-blue:focus:border-blue-400 theme-blue:focus:text-blue-50 text-sm"
                    required
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    title={showPassword ? "Hide password" : "Show password"}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className={`absolute right-3 top-2.5 p-0.5 rounded transition-colors cursor-pointer ${
                      showPassword
                        ? "text-indigo-600 dark:text-indigo-400 theme-blue:text-cyan-400"
                        : "text-slate-400 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 theme-blue:text-blue-400 theme-blue:hover:text-blue-200"
                    }`}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500 theme-blue:bg-blue-600 theme-blue:hover:bg-blue-500 text-white font-semibold py-2.5 shadow-lg shadow-indigo-600/20 dark:shadow-indigo-600/30 theme-blue:shadow-blue-600/30 transition-all cursor-pointer"
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center space-x-2">
                    <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Signing in...</span>
                  </span>
                ) : (
                  <span className="flex items-center justify-center space-x-2">
                    <span>Sign In</span>
                    <ArrowRight className="h-4 w-4" />
                  </span>
                )}
              </Button>
            </form>

            {/* Quick Demo Role Selector Buttons
            <div className="pt-4 border-t border-slate-200 dark:border-slate-800/80 theme-blue:border-[#1c2d58] space-y-3">
              <div className="text-center space-y-0.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 theme-blue:text-blue-300 block">
                  Quick Role Login (Frappe Role Integration)
                </span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 theme-blue:text-blue-400/80 block">
                  Click any account to automatically test its role-based workspace
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleQuickLogin("admin@ems.com", "SarahJenkins")}
                  className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-indigo-50/80 hover:bg-indigo-100/90 border border-indigo-200/80 text-indigo-700 dark:bg-indigo-950/60 dark:hover:bg-indigo-900 dark:border-indigo-800/50 dark:text-indigo-200 theme-blue:bg-[#192a54]/80 theme-blue:hover:bg-[#1f356b] theme-blue:border-[#254284] theme-blue:text-indigo-200 text-xs font-medium transition-all hover:scale-[1.02] cursor-pointer"
                >
                  <div className="flex items-center space-x-1.5 mb-0.5">
                    <Shield className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400 theme-blue:text-indigo-300" />
                    <span className="font-semibold">Administrator</span>
                  </div>
                  <span className="text-[10px] text-indigo-600/80 dark:text-indigo-300/70 theme-blue:text-indigo-300/70">admin@ems.com</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleQuickLogin("hr@ems.com", "AlexRivera")}
                  className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-emerald-50/80 hover:bg-emerald-100/90 border border-emerald-200/80 text-emerald-700 dark:bg-emerald-950/60 dark:hover:bg-emerald-900 dark:border-emerald-800/50 dark:text-emerald-200 theme-blue:bg-emerald-950/50 theme-blue:hover:bg-emerald-900/70 theme-blue:border-emerald-800/50 theme-blue:text-emerald-200 text-xs font-medium transition-all hover:scale-[1.02] cursor-pointer"
                >
                  <div className="flex items-center space-x-1.5 mb-0.5">
                    <UserCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 theme-blue:text-emerald-300" />
                    <span className="font-semibold">HR Manager</span>
                  </div>
                  <span className="text-[10px] text-emerald-600/80 dark:text-emerald-300/70 theme-blue:text-emerald-300/70">hr@ems.com</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleQuickLogin("employee@ems.com", "DavidChen")}
                  className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-blue-50/80 hover:bg-blue-100/90 border border-blue-200/80 text-blue-700 dark:bg-blue-950/60 dark:hover:bg-blue-900 dark:border-blue-800/50 dark:text-blue-200 theme-blue:bg-[#14234b]/80 theme-blue:hover:bg-[#1a3068] theme-blue:border-[#223f7e] theme-blue:text-blue-200 text-xs font-medium transition-all hover:scale-[1.02] cursor-pointer"
                >
                  <div className="flex items-center space-x-1.5 mb-0.5">
                    <Users className="h-3.5 w-3.5 text-blue-600 dark:text-cyan-400 theme-blue:text-cyan-300" />
                    <span className="font-semibold">Employee</span>
                  </div>
                  <span className="text-[10px] text-blue-600/80 dark:text-blue-300/70 theme-blue:text-blue-300/70">employee@ems.com</span>
                </button>
              </div> */}
{/* 
              Extra Frappe Administrator shortcut
              <div className="pt-1 flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400 theme-blue:text-blue-300 bg-slate-100/80 dark:bg-slate-800/40 theme-blue:bg-[#18274d]/50 px-3 py-1.5 rounded-lg border border-slate-200/80 dark:border-slate-700/40 theme-blue:border-[#24396b]/50">
                <span>Frappe Core Admin:</span>
                <button
                  type="button"
                  onClick={() => handleQuickLogin("admin@example.com", "Tech@123")}
                  className="text-indigo-600 dark:text-indigo-400 theme-blue:text-blue-400 hover:underline font-mono font-medium cursor-pointer"
                >
                  Administrator / admin
                </button>
              </div> */}
            {/* </div> */}
          </CardContent>
        </Card>

        <p className="text-center text-xs text-slate-400 dark:text-slate-500 theme-blue:text-blue-400/60">
          Frappe Framework + React 19 Enterprise Workspace
        </p>
      </div>
    </div>
  );
}
