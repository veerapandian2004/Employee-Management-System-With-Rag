import { useState } from "react";
import { CalendarOff, Plus, Edit, Trash2, CheckCircle2, ShieldCheck, AlertCircle } from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";

export function LeaveTypeModule({
  leaveTypes = [],
  userRole = "Administrator",
  onAddLeaveType,
  onUpdateLeaveType,
  onDeleteLeaveType,
}) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingLT, setEditingLT] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const canManage = userRole === "Administrator" || userRole === "HR";

  const initialForm = {
    leave_type_name: "",
    max_days_per_year: 12,
    carry_forward: false,
  };

  const [formData, setFormData] = useState(initialForm);

  const handleOpenAdd = () => {
    setFormData(initialForm);
    setEditingLT(null);
    setErrorMsg("");
    setIsAddOpen(true);
  };

  const handleOpenEdit = (lt) => {
    setEditingLT(lt);
    setFormData({
      leave_type_name: lt.leave_type_name || lt.name || "",
      max_days_per_year: lt.max_days_per_year || 12,
      carry_forward: Boolean(lt.carry_forward),
    });
    setErrorMsg("");
    setIsAddOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.leave_type_name.trim()) return;

    try {
      if (editingLT) {
        await onUpdateLeaveType(editingLT.name, formData);
      } else {
        await onAddLeaveType(formData);
      }
      setIsAddOpen(false);
    } catch (err) {
      setErrorMsg(err.message || "Failed to save leave type.");
    }
  };

  const carryForwardCount = leaveTypes.filter((lt) => lt.carry_forward).length;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <CalendarOff className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>Leave Type Configurations</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Configure leave policies, annual allowances, and carry-forward rules
          </p>
        </div>

        {canManage && (
          <Button onClick={handleOpenAdd} className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer">
            <Plus className="mr-2 h-4 w-4" /> Add Leave Type
          </Button>
        )}
      </div>

      {/* Policy KPI Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Active Leave Types</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{leaveTypes.length} Policies</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-indigo-50 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <CalendarOff className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Carry Forward Enabled</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{carryForwardCount} Types</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-emerald-50 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Avg Days / Year</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {leaveTypes.length > 0
                  ? Math.round(
                      leaveTypes.reduce((acc, curr) => acc + Number(curr.max_days_per_year || 0), 0) /
                        leaveTypes.length
                    )
                  : 0}{" "}
                Days
              </h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-purple-50 dark:bg-purple-950/80 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Cards Grid of Leave Types */}
      {leaveTypes.length === 0 ? (
        <Card className="p-12 text-center text-slate-500">
          <CalendarOff className="h-12 w-12 mx-auto mb-3 opacity-40 text-indigo-500" />
          <h3 className="text-base font-semibold text-slate-700 dark:text-slate-300">No Leave Policies Configured</h3>
          <p className="text-xs text-slate-400 mt-1">Click Add Leave Type above to set up standard leave categories.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {leaveTypes.map((lt) => (
            <Card key={lt.name} className="border border-slate-200 dark:border-slate-800 hover:shadow-md transition-all">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-start justify-between">
                  <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base">{lt.leave_type_name}</h3>
                  <Badge variant={lt.carry_forward ? "success" : "secondary"} className="text-xs">
                    {lt.carry_forward ? "Carry Forward" : "No Rollover"}
                  </Badge>
                </div>

                <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-lg border border-slate-100 dark:border-slate-700 flex items-center justify-between">
                  <span className="text-xs text-slate-500 dark:text-slate-400">Max Allowance</span>
                  <span className="text-lg font-extrabold text-indigo-600 dark:text-indigo-400">
                    {lt.max_days_per_year} Days / yr
                  </span>
                </div>

                {canManage && (
                  <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 text-xs cursor-pointer"
                      onClick={() => handleOpenEdit(lt)}
                    >
                      <Edit className="mr-1 h-3.5 w-3.5" /> Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                      onClick={() => onDeleteLeaveType(lt.name)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add / Edit Dialog */}
      {canManage && (
        <Dialog
          isOpen={isAddOpen}
          onClose={() => setIsAddOpen(false)}
          title={editingLT ? "Edit Leave Type Policy" : "Create Leave Type Policy"}
          description="Configure Leave Type DocType fields."
          maxWidth="max-w-md"
        >
          <form onSubmit={handleSave} className="space-y-4 py-2">
            {errorMsg && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-rose-600 dark:text-rose-400 text-xs flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Leave Type Name *
              </label>
              <Input
                placeholder="e.g. Parental Leave"
                value={formData.leave_type_name}
                onChange={(e) => setFormData({ ...formData, leave_type_name: e.target.value })}
                required
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Max Days Per Year
              </label>
              <Input
                type="number"
                value={formData.max_days_per_year}
                onChange={(e) => setFormData({ ...formData, max_days_per_year: Number(e.target.value) })}
                required
              />
            </div>

            <div className="flex items-center space-x-3 pt-2">
              <input
                type="checkbox"
                id="carry_forward"
                checked={formData.carry_forward}
                onChange={(e) => setFormData({ ...formData, carry_forward: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 dark:border-slate-600 dark:bg-slate-800 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
              />
              <label htmlFor="carry_forward" className="text-xs font-semibold text-slate-700 dark:text-slate-300 cursor-pointer">
                Allow Carry Forward to Next Year
              </label>
            </div>

            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-3">
              <Button type="button" variant="outline" onClick={() => setIsAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 font-semibold cursor-pointer">
                Save Policy
              </Button>
            </div>
          </form>
        </Dialog>
      )}
    </div>
  );
}
