"use client"

import { useState, useCallback } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Check,
  ChevronDown,
  Loader2,
  AlertCircle,
  ExternalLink,
  FileText,
  ImageIcon,
  ArrowRight,
  RotateCcw,
  Sparkles,
  Radio,
  CircleDashed,
  XCircle,
  HelpCircle,
} from "lucide-react"
import { useIngestionJob, useRerunJob } from "@/hooks/use-ingestion"
import { useIngestionSSE } from "@/hooks/use-ingestion-sse"
import { IngestionProgressSkeleton } from "@/components/skeletons"
import type { IngestionSSEPayload } from "@kama/contracts"

type AgentEvent = {
  id: string
  type: string
  message: string
  timestamp: string
}

const processingSteps = [
  { key: "reading", label: "Reading source", description: "Fetching and analyzing content" },
  { key: "extracting", label: "Extracting recipe", description: "Parsing ingredients, steps, and metadata" },
  { key: "reviewing", label: "Reviewing & enriching", description: "AI verifying and filling gaps" },
  { key: "ready", label: "Ready for review", description: "Recipe is ready for your review" },
]

function internalStateToStep(state: string | undefined): number {
  switch (state) {
    case "source_received":
    case "source_normalization":
      return 0
    case "extraction_plan_building":
    case "recipe_extraction":
      return 1
    case "quality_assessment":
    case "review_agent_processing":
      return 2
    case "completed":
      return 3
    default:
      return 0
  }
}

export default function IngestionProgressPage() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.jobId as string

  const { data: job, isLoading, isError, refetch } = useIngestionJob(jobId)
  const rerunJob = useRerunJob()

  const [events, setEvents] = useState<AgentEvent[]>([])
  const [timelineOpen, setTimelineOpen] = useState(false)

  const handleSSEEvent = useCallback((payload: IngestionSSEPayload) => {
    setEvents((prev) => [
      ...prev,
      {
        id: `${payload.sequence}`,
        type: payload.eventType,
        message: `${payload.eventType}: ${payload.status}${payload.methodKey ? ` (${payload.methodKey})` : ""}${payload.reasoning ? ` — ${payload.reasoning}` : ""}`,
        timestamp: new Date(payload.timestamp).toLocaleTimeString(),
      },
    ])
  }, [])

  const isTerminal = job?.status && ["review_ready", "draft_ready", "failed", "unsupported"].includes(job.status)

  useIngestionSSE(
    isTerminal ? "" : jobId,
    handleSSEEvent,
  )

  const status = job?.status ?? "queued"
  const currentStep = job ? internalStateToStep(job.internalState) : 0
  const candidateId = job?.candidateId

  const handleRerun = () => {
    rerunJob.mutate(jobId, {
      onSuccess: (result) => {
        router.push(`/ingest/${result.newJobId}`)
      },
    })
  }

  const getStepIcon = (stepIndex: number) => {
    if (stepIndex < currentStep) return <Check className="h-4 w-4 text-background" />
    if (stepIndex === currentStep && (status === "processing" || status === "queued"))
      return <Loader2 className="h-4 w-4 text-background animate-spin" />
    if (stepIndex === currentStep && (status === "review_ready" || status === "draft_ready"))
      return <Check className="h-4 w-4 text-background" />
    return <CircleDashed className="h-4 w-4 text-muted-foreground" />
  }

  const getStepStyle = (stepIndex: number) => {
    if (stepIndex < currentStep) return "bg-foreground"
    if (stepIndex === currentStep && status !== "queued") return "bg-foreground"
    return "bg-muted"
  }

  const getEventIcon = (event: AgentEvent) => {
    if (event.type.includes("succeeded") || event.type.includes("completed")) return <Check className="h-3 w-3 text-green-600" />
    if (event.type.includes("failed") || event.type.includes("error")) return <XCircle className="h-3 w-3 text-destructive" />
    if (event.type.includes("started") || event.type.includes("running")) return <Radio className="h-3 w-3 text-muted-foreground" />
    if (event.type.includes("state")) return <Sparkles className="h-3 w-3 text-foreground" />
    return <CircleDashed className="h-3 w-3 text-muted-foreground" />
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <IngestionProgressSkeleton />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-7 w-7 text-destructive" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load job</h3>
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">Something went wrong.</p>
        <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
          <RotateCcw className="h-4 w-4 mr-1" /> Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Processing Recipe</h1>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/ingest">New source</Link>
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-8">
        {/* Source Preview */}
        <Card className="border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                <FileText className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground line-clamp-1">Job {jobId}</p>
                <p className="mt-0.5 text-xs text-muted-foreground truncate">Status: {status}</p>
              </div>
              <Badge variant="secondary" className="shrink-0 font-normal text-xs">{status}</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Progress Steps */}
        <Card className="mt-6 border-0 shadow-sm">
          <CardContent className="p-6">
            <div className="space-y-6">
              {processingSteps.map((step, index) => (
                <div key={step.key} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-full transition-colors ${getStepStyle(index)}`}>
                      {getStepIcon(index)}
                    </div>
                    {index < processingSteps.length - 1 && (
                      <div className={`mt-1 h-8 w-px transition-colors ${index < currentStep ? "bg-foreground" : "bg-border"}`} />
                    )}
                  </div>
                  <div className="pt-1">
                    <p className={`text-sm font-medium transition-colors ${index <= currentStep ? "text-foreground" : "text-muted-foreground"}`}>{step.label}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{step.description}</p>
                  </div>
                </div>
              ))}
            </div>

            {status === "review_ready" && candidateId && (
              <div className="mt-8 rounded-lg bg-muted/50 p-4 text-center">
                <p className="text-sm font-medium text-foreground">Recipe extracted successfully</p>
                <Button className="mt-4" asChild>
                  <Link href={`/ingest/${jobId}/review`}>Review Recipe<ArrowRight className="h-4 w-4 ml-2" /></Link>
                </Button>
              </div>
            )}

            {status === "draft_ready" && candidateId && (
              <div className="mt-8 rounded-lg bg-muted/50 p-4 text-center">
                <div className="flex items-center justify-center gap-2">
                  <HelpCircle className="h-4 w-4 text-muted-foreground" />
                  <p className="text-sm font-medium text-foreground">Partial recipe found</p>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">Some fields couldn&apos;t be extracted. You can review and complete it as a draft.</p>
                <Button className="mt-4" asChild>
                  <Link href={`/ingest/${jobId}/review`}>Review as Draft<ArrowRight className="h-4 w-4 ml-2" /></Link>
                </Button>
              </div>
            )}

            {status === "failed" && (
              <div className="mt-8 rounded-lg bg-destructive/5 p-4 text-center">
                <AlertCircle className="h-5 w-5 text-destructive mx-auto" />
                <p className="mt-2 text-sm font-medium text-foreground">Extraction failed</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {job?.errorCode ?? "We couldn't extract a recipe from this source."}
                </p>
                <div className="mt-4 flex items-center justify-center gap-3">
                  {job?.rerunAllowed && (
                    <Button variant="outline" size="sm" onClick={handleRerun} disabled={rerunJob.isPending}>
                      <RotateCcw className="h-4 w-4 mr-1" />{rerunJob.isPending ? "Retrying..." : "Try Again"}
                    </Button>
                  )}
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/ingest">Try Different Source</Link>
                  </Button>
                </div>
              </div>
            )}

            {status === "unsupported" && (
              <div className="mt-8 rounded-lg bg-muted/50 p-4 text-center">
                <HelpCircle className="h-5 w-5 text-muted-foreground mx-auto" />
                <p className="mt-2 text-sm font-medium text-foreground">Couldn&apos;t find a recipe</p>
                <p className="mt-1 text-xs text-muted-foreground">This source doesn&apos;t appear to contain a recipe we can extract.</p>
                <Button variant="outline" size="sm" className="mt-4" asChild>
                  <Link href="/ingest">Try Different Source</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Agent Timeline */}
        {events.length > 0 && (
          <Card className="mt-6 border-0 shadow-sm">
            <Collapsible open={timelineOpen} onOpenChange={setTimelineOpen}>
              <CollapsibleTrigger asChild>
                <CardContent className="p-4 cursor-pointer hover:bg-muted/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">Agent activity</span>
                      <Badge variant="secondary" className="font-normal text-xs">{events.length} events</Badge>
                    </div>
                    <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${timelineOpen ? "rotate-180" : ""}`} />
                  </div>
                </CardContent>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <CardContent className="px-4 pb-4 pt-0">
                  <div className="space-y-2">
                    {events.map((event) => (
                      <div key={event.id} className="flex items-start gap-3 py-1">
                        <div className="mt-1">{getEventIcon(event)}</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-foreground">{event.message}</p>
                        </div>
                        <span className="text-xs text-muted-foreground shrink-0 tabular-nums">{event.timestamp}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}
      </div>
    </div>
  )
}
