import type { HTMLAttributes, ReactNode } from "react";

export function Badge({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full bg-stone-800 px-2 py-0.5 text-xs text-stone-200 ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}
