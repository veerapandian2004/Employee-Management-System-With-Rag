import React from "react";
import { cn } from "./utils";

export const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-lg border border-slate-300 bg-white px-3 py-1 text-sm text-slate-900 shadow-xs transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus:outline-none caret-indigo-600 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50 dark:placeholder:text-slate-400 dark:focus-visible:ring-indigo-400 dark:focus:bg-slate-900 dark:focus:text-slate-50 dark:caret-indigo-400 theme-blue:border-[#24396b] theme-blue:bg-[#18274d] theme-blue:text-blue-50 theme-blue:placeholder:text-blue-400 theme-blue:focus-visible:ring-blue-400 theme-blue:focus:bg-[#18274d] theme-blue:focus:text-blue-50 theme-blue:caret-cyan-400",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});

Input.displayName = "Input";
