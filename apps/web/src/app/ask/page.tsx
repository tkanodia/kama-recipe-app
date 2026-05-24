"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { MessageCircle, Send, Loader2 } from "lucide-react"
import { useCreateAskSession } from "@/hooks/use-ask"

const SUGGESTED_QUESTIONS = [
  "What can I make with chicken and rice?",
  "Which of my recipes is quickest to prepare?",
  "Any pasta recipes good for meal prep?",
]

export default function AskPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [question, setQuestion] = useState("")
  const createSession = useCreateAskSession()

  useEffect(() => {
    const q = searchParams.get("q")
    if (q) setQuestion(q)
  }, [searchParams])

  const handleSubmit = (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || createSession.isPending) return

    createSession.mutate(
      { question: trimmed },
      {
        onSuccess: (data) => {
          router.push(`/ask/${data.sessionId}`)
        },
      },
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <MessageCircle className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Ask Kama</h1>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-6">
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-orange-500/10">
            <MessageCircle className="h-8 w-8 text-orange-500" />
          </div>
          <h2 className="mt-6 text-2xl font-bold text-foreground">
            Ask Kama
          </h2>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Get expert cooking advice, find recipes by ingredients, and get
            personalized tips from your recipe collection.
          </p>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium text-muted-foreground">
            Try asking...
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {SUGGESTED_QUESTIONS.map((q) => (
              <Card
                key={q}
                className="cursor-pointer border border-border hover:border-foreground/20 transition-colors"
                onClick={() => handleSubmit(q)}
              >
                <CardContent className="p-4">
                  <p className="text-sm text-foreground leading-relaxed">{q}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div className="mt-8">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSubmit(question)
            }}
            className="flex items-center gap-2"
          >
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask anything about your recipes..."
              disabled={createSession.isPending}
              autoFocus
            />
            <Button
              type="submit"
              disabled={!question.trim() || createSession.isPending}
            >
              {createSession.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
          {createSession.isError && (
            <p className="mt-2 text-sm text-destructive">
              Something went wrong. Please try again.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
