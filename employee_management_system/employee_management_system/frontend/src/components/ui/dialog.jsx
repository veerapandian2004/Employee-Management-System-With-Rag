import { X } from "lucide-react";
import { cn } from "./utils";

export function Dialog({ isOpen, onClose, title, description, children, maxWidth = "max-w-md" }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-200 print:static print:inset-auto print:p-0 print:bg-transparent print:backdrop-blur-none print:block">
      <div 
        className={cn(
          "relative w-full bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] p-6 max-h-[90vh] overflow-y-auto print:shadow-none print:border-none print:max-h-none print:overflow-visible print:p-2 print:text-black",
          maxWidth
        )}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 dark:hover:text-slate-200 p-1 rounded-lg transition-colors cursor-pointer print:hidden"
          title="Close dialog"
        >
          <X className="h-5 w-5" />
        </button>

        {title && (
          <div className="mb-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">{title}</h3>
            {description && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{description}</p>
            )}
          </div>
        )}

        {children}
      </div>
    </div>
  );
}
