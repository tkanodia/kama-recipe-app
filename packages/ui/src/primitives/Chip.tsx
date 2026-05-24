import type { HTMLAttributes, ReactNode } from "react";

export function Chip({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border border-stone-600 bg-stone-900 px-2 py-1 text-xs text-stone-200 ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}
