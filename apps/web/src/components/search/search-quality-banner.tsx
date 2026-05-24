import { AlertCircle } from "lucide-react"

export function SearchQualityBanner() {
  return (
    <div className="mt-3 rounded-md border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm text-orange-400 flex items-center gap-2">
      <AlertCircle className="h-4 w-4 shrink-0" />
      Search quality reduced — using basic text matching as a fallback.
    </div>
  )
}
