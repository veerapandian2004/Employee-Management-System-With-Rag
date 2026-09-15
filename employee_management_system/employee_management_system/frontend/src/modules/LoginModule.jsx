import { useState } from "react";
import { Sparkles, Lock, Mail, AlertCircle, ArrowRight, Shield, UserCheck, Users, Eye, EyeOff } from "lucide-react";
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
    <div className="min-h-screen flex flex-col justify-center items-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-4 sm:p-6 text-slate-100">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500 to-cyan-400 text-white shadow-xl shadow-indigo-500/20 mb-2">
            <Sparkles className="h-7 w-7" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Employee Management System
          </h1>
          <p className="text-sm text-indigo-200/80">
            Sign in to access your dashboard, leaves, records, and HR workspace
          </p>
        </div>

        {/* Login Form Card */}
        <Card className="bg-slate-900/80 border-slate-800 shadow-2xl backdrop-blur-xl">
          <CardContent className="p-6 sm:p-8 space-y-5">
            {error && (
              <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center space-x-2.5 animate-in fade-in duration-200">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 block">
                  Email / Username
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
                  <Input
                    type="text"
                    placeholder="admin@ems.com"
                    value={usr}
                    onChange={(e) => setUsr(e.target.value)}
                    className="pl-10 bg-slate-800/80 border-slate-700 text-white placeholder:text-slate-500 text-sm focus:border-indigo-500"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-300 block">
                    Password
                  </label>
                  <span className="text-[10px] text-indigo-300/80 font-normal">
                    Full name without space (e.g. SarahJenkins)
                  </span>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="e.g. SarahJenkins"
                    value={pwd}
                    onChange={(e) => setPwd(e.target.value)}
                    className="pl-10 pr-10 bg-slate-800/80 border-slate-700 text-white placeholder:text-slate-500 text-sm focus:border-indigo-500"
                    required
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
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

            {/* Quick Demo Role Selector Buttons */}
            <div className="pt-4 border-t border-slate-800/80 space-y-3">
              <div className="text-center space-y-0.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
                  Quick Role Login (Frappe Role Integration)
                </span>
                <span className="text-[10px] text-slate-500 block">
                  Click any account to automatically test its role-based workspace
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleQuickLogin("admin@ems.com", "SarahJenkins")}
                  className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900 border border-indigo-800/50 text-indigo-200 text-xs font-medium transition-all hover:scale-[1.02] cursor-pointer"
                >
                  <div className="flex items-center space-x-1.5 mb-0.5">
                    <Shield className="h-3.5 w-3.5 text-indigo-400" />
                    <span className="font-semibold">Administrator</span>
                  </div>
                  <span className="text-[10px] text-indigo-300/70">admin@ems.com</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleQuickLogin("hr@ems.com", "AlexRivera")}
                  className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-800/50 text-emerald-200 text-xs font-medium transition-all hover:scale-[1.02] cursor-pointer"
                >
                  <div className="flex items-center space-x-1.5 mb-0.5">
                    <UserCheck className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="font-semibold">HR Manager</span>
                  </div>
                  <span className="text-[10px] text-emerald-300/70">hr@ems.com</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleQuickLogin("employee@ems.com", "DavidChen")}
                  className="flex flex-col items-center justify-center p-2.5 rounded-lg bg-blue-950/60 hover:bg-blue-900 border border-blue-800/50 text-blue-200 text-xs font-medium transition-all hover:scale-[1.02] cursor-pointer"
                >
                  <div className="flex items-center space-x-1.5 mb-0.5">
                    <Users className="h-3.5 w-3.5 text-cyan-400" />
                    <span className="font-semibold">Employee</span>
                  </div>
                  <span className="text-[10px] text-blue-300/70">employee@ems.com</span>
                </button>
              </div>

              {/* Extra Frappe Administrator shortcut */}
              <div className="pt-1 flex items-center justify-between text-[11px] text-slate-400 bg-slate-800/40 px-3 py-1.5 rounded-lg border border-slate-700/40">
                <span className="text-slate-400">Frappe Core Admin:</span>
                <button
                  type="button"
                  onClick={() => handleQuickLogin("admin@example.com", "Tech@123")}
                  className="text-indigo-400 hover:text-indigo-300 font-mono font-medium hover:underline cursor-pointer"
                >
                  Administrator / admin
                </button>
              </div>
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-slate-500">
          Frappe Framework + React 19 Enterprise Workspace
        </p>
      </div>
    </div>
  );
}
