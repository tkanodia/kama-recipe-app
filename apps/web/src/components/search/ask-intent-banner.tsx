import Link from "next/link"
import { MessageCircle } from "lucide-react"

export function AskIntentBanner({ query }: { query: string }) {
  return (
    <Link
      href={`/ask?q=${encodeURIComponent(query)}`}
      className="mt-4 flex items-center gap-3 rounded-md border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-400 hover:bg-blue-500/20 transition-colors"
    >
      <MessageCircle className="h-4 w-4 shrink-0" />
      <span>
        This looks like a question.{" "}
        <span className="font-medium underline">Try asking Kama</span>
      </span>
    </Link>
  )
}
