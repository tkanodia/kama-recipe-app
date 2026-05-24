"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  MessageCircle,
  Send,
  Loader2,
  AlertCircle,
  RotateCcw,
  XCircle,
  Clock,
  Plus,
  Copy,
  Check,
  Mic,
  MicOff,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react"
import {
  useAskSession,
  useSendMessageStream,
  useCloseAskSession,
  useAskSessions,
} from "@/hooks/use-ask"
import { useRecipe } from "@/hooks/use-recipes"
import type { AskMessage, AskSessionListItem } from "@kama/contracts"

const REC_ID_RE = /\s*\[rec_[a-z0-9]+\]/g

function stripRecIds(text: string): string {
  return text.replace(REC_ID_RE, "")
}

export default function AskSessionPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params.sessionId as string
  const [input, setInput] = useState("")
  const [pendingUserMsg, setPendingUserMsg] = useState<string | null>(null)
  const [streamingText, setStreamingText] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const {
    data: session,
    isLoading,
    isError,
    refetch,
  } = useAskSession(sessionId)

  const { send: sendStream } = useSendMessageStream(sessionId)
  const closeSession = useCloseAskSession()

  const isClosed = session?.status === "closed"

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [session?.messages, streamingText, pendingUserMsg])

  const handleSend = useCallback((text?: string) => {
    const trimmed = (text ?? input).trim()
    if (!trimmed || isSending || isClosed) return

    setPendingUserMsg(trimmed)
    setStreamingText("")
    setIsSending(true)
    setInput("")

    sendStream(trimmed, {
      onToken: (t) => {
        setStreamingText((prev) => (prev ?? "") + t)
      },
      onDone: () => {
        setPendingUserMsg(null)
        setStreamingText(null)
        setIsSending(false)
      },
      onError: () => {
        setStreamingText((prev) =>
          (prev || "") + "\n\n[Error: generation failed]"
        )
        setPendingUserMsg(null)
        setIsSending(false)
      },
    })
  }, [input, isSending, isClosed, sendStream])

  const handleNewChat = () => {
    closeSession.mutate(sessionId)
    router.push("/ask")
  }

  if (isLoading) {
    return (
      <div className="flex h-screen bg-background">
        <div className="flex flex-1 flex-col">
          <SessionHeader onNewChat={handleNewChat} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <div className="flex flex-1 flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="mt-3 text-sm text-muted-foreground">
              Loading conversation...
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (isError || !session) {
    return (
      <div className="flex h-screen bg-background">
        <div className="flex flex-1 flex-col">
          <SessionHeader onNewChat={handleNewChat} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
              <AlertCircle className="h-7 w-7 text-destructive" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">
              Failed to load session
            </h3>
            <p className="mt-2 max-w-sm text-sm text-muted-foreground">
              Something went wrong. Please try again.
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => void refetch()}
            >
              <RotateCcw className="h-4 w-4 mr-1" />
              Retry
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Session Sidebar */}
      {sidebarOpen && (
        <SessionSidebar
          currentSessionId={sessionId}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex flex-1 flex-col min-w-0">
        <SessionHeader
          onNewChat={handleNewChat}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        {isClosed && (
          <div className="border-b border-orange-500/30 bg-orange-500/10 px-4 py-2 text-center text-sm text-orange-400 flex items-center justify-center gap-2">
            <XCircle className="h-4 w-4" />
            This session has been closed.
            <Link href="/ask" className="underline hover:text-orange-300">
              Start a new conversation
            </Link>
          </div>
        )}

        {/* Scrollable messages area */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-2xl px-4 py-6 space-y-4">
            {session.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {pendingUserMsg && (
              <div className="flex items-start gap-3 flex-row-reverse">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-foreground/10">
                  <span className="text-xs font-medium text-foreground">You</span>
                </div>
                <div className="max-w-[80%] rounded-lg px-4 py-3 bg-foreground/5 text-foreground">
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{pendingUserMsg}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
              </div>
            )}

            {streamingText !== null && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-orange-500/10">
                  <MessageCircle className="h-4 w-4 text-orange-500" />
                </div>
                <div className="max-w-[80%] rounded-lg px-4 py-3 bg-muted text-foreground">
                  {streamingText ? (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {stripRecIds(streamingText)}
                      <span className="inline-block w-1.5 h-4 bg-orange-500 animate-pulse ml-0.5 align-middle rounded-sm" />
                    </p>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="h-2 w-2 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="h-2 w-2 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  )}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Fixed input bar at bottom */}
        <div className="shrink-0 border-t border-border bg-background p-4">
          <div className="mx-auto max-w-2xl">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              className="flex items-center gap-2"
            >
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  isClosed
                    ? "Session closed"
                    : "Ask a follow-up question..."
                }
                disabled={isSending || isClosed}
              />
              <VoiceInputButton
                onResult={(transcript) => {
                  setInput(transcript)
                }}
                disabled={isSending || isClosed}
              />
              <Button
                type="submit"
                disabled={!input.trim() || isSending || isClosed}
              >
                {isSending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

function SessionHeader({
  onNewChat,
  onToggleSidebar,
}: {
  onNewChat: () => void
  onToggleSidebar: () => void
}) {
  return (
    <div className="shrink-0 border-b border-border bg-background">
      <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleSidebar}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Toggle history"
          >
            <PanelLeftOpen className="h-5 w-5" />
          </button>
          <Link
            href="/ask"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            &larr; Back
          </Link>
          <MessageCircle className="h-5 w-5 text-foreground ml-1" />
          <h1 className="text-lg font-semibold text-foreground">Ask Kama</h1>
        </div>
        <Button variant="outline" size="sm" onClick={onNewChat}>
          <Plus className="h-4 w-4 mr-1" />
          New Chat
        </Button>
      </div>
    </div>
  )
}

// --- Session Sidebar ---

function SessionSidebar({
  currentSessionId,
  onClose,
}: {
  currentSessionId: string
  onClose: () => void
}) {
  const { data, isLoading } = useAskSessions()

  return (
    <div className="w-72 shrink-0 border-r border-border bg-muted/30 flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border">
        <h2 className="text-sm font-semibold text-foreground">Chat History</h2>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
        {data?.items.map((s) => (
          <SessionListItem
            key={s.sessionId}
            session={s}
            isActive={s.sessionId === currentSessionId}
          />
        ))}
        {data && data.items.length === 0 && (
          <p className="px-4 py-8 text-center text-xs text-muted-foreground">
            No conversations yet
          </p>
        )}
      </div>
    </div>
  )
}

function SessionListItem({
  session,
  isActive,
}: {
  session: AskSessionListItem
  isActive: boolean
}) {
  const timeAgo = formatRelativeTime(session.lastActiveAt)

  return (
    <Link
      href={`/ask/${session.sessionId}`}
      className={`block px-4 py-2.5 transition-colors ${
        isActive
          ? "bg-orange-500/10 border-r-2 border-orange-500"
          : "hover:bg-muted"
      }`}
    >
      <p
        className={`text-sm line-clamp-1 ${
          isActive ? "font-medium text-foreground" : "text-foreground/80"
        }`}
      >
        {session.preview || "New conversation"}
      </p>
      <div className="flex items-center gap-2 mt-0.5">
        <span className="text-xs text-muted-foreground">{timeAgo}</span>
        {session.status === "closed" && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
            closed
          </span>
        )}
      </div>
    </Link>
  )
}

function formatRelativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(isoDate).toLocaleDateString([], { month: "short", day: "numeric" })
}

// --- Voice Input ---

function VoiceInputButton({
  onResult,
  disabled,
}: {
  onResult: (transcript: string) => void
  disabled: boolean
}) {
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const toggleListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }

    const SpeechRecognition =
      window.SpeechRecognition ?? window.webkitSpeechRecognition

    if (!SpeechRecognition) return

    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = "en-US"

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0]?.[0]?.transcript
      if (transcript) {
        onResult(transcript)
      }
      setIsListening(false)
    }

    recognition.onerror = () => {
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }, [isListening, onResult])

  const hasSpeechApi =
    typeof window !== "undefined" &&
    (("SpeechRecognition" in window) || ("webkitSpeechRecognition" in window))

  if (!hasSpeechApi) return null

  return (
    <Button
      type="button"
      variant={isListening ? "destructive" : "outline"}
      size="icon"
      onClick={toggleListening}
      disabled={disabled}
      title={isListening ? "Stop listening" : "Voice input"}
    >
      {isListening ? (
        <MicOff className="h-4 w-4" />
      ) : (
        <Mic className="h-4 w-4" />
      )}
    </Button>
  )
}

// --- Message Bubble ---

function MessageBubble({ message }: { message: AskMessage }) {
  const isUser = message.role === "user"
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(stripRecIds(message.content))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`group flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-foreground/10"
            : "bg-orange-500/10"
        }`}
      >
        {isUser ? (
          <span className="text-xs font-medium text-foreground">You</span>
        ) : (
          <MessageCircle className="h-4 w-4 text-orange-500" />
        )}
      </div>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-foreground/5 text-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {isUser ? message.content : stripRecIds(message.content)}
        </p>
        {!isUser &&
          message.citedRecipeIds &&
          message.citedRecipeIds.length > 0 && (
            <div className="mt-3 space-y-2">
              {message.citedRecipeIds.map((id) => (
                <CitedRecipeCard key={id} recipeId={id} />
              ))}
            </div>
          )}
        <div className="mt-1 flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            {new Date(message.createdAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
          {!isUser && (
            <button
              onClick={handleCopy}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
              title="Copy response"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Cited Recipe Card ---

function CitedRecipeCard({ recipeId }: { recipeId: string }) {
  const { data: recipe, isLoading } = useRecipe(recipeId)

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-md border border-border p-2 animate-pulse">
        <div className="h-12 w-12 rounded bg-muted shrink-0" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3 w-24 rounded bg-muted" />
          <div className="h-2.5 w-16 rounded bg-muted" />
        </div>
      </div>
    )
  }

  if (!recipe) return null

  const totalTime =
    (recipe.prepTimeMinutes ?? 0) + (recipe.cookTimeMinutes ?? 0)
  const heroUrl = (recipe.heroImage as { assetRef?: string } | undefined)?.assetRef

  return (
    <Link
      href={`/recipes/${recipeId}`}
      className="flex items-center gap-3 rounded-md border border-border bg-background p-2 hover:border-orange-500/40 transition-colors group"
    >
      <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded bg-muted">
        {heroUrl ? (
          <Image
            src={heroUrl}
            alt={recipe.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-200"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <span className="text-base font-bold text-muted-foreground/30">
              {recipe.title.charAt(0)}
            </span>
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-orange-500 group-hover:text-orange-400 line-clamp-1 transition-colors">
          {recipe.title}
        </p>
        {totalTime > 0 && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
            <Clock className="h-3 w-3" />
            {totalTime} min
          </div>
        )}
      </div>
    </Link>
  )
}
