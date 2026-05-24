import type { TextareaHTMLAttributes } from "react";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className = "", ...rest }: TextareaProps) {
  return (
    <textarea
      className={`w-full rounded-md border border-stone-600 bg-stone-900 px-3 py-2 text-stone-100 placeholder:text-stone-500 focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500 ${className}`}
      {...rest}
    />
  );
}
