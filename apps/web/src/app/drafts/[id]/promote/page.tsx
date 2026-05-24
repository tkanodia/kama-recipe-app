"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter, useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Check,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Loader2,
  Shield,
  ArrowRight,
  RotateCcw,
} from "lucide-react"
import { useDraft, useReviewForCanonical, usePromoteDraft } from "@/hooks/use-drafts"
import { Skeleton } from "@/components/ui/skeleton"

type AssessmentStatus = "assessing" | "eligible" | "not_eligible"

export default function DraftPromotionPage() {
  const router = useRouter()
  const params = useParams()
  const draftId = params.id as string

  const { data: draft, isLoading: draftLoading, isError: draftError, refetch } = useDraft(draftId)
  const { data: assessment, refetch: fetchAssessment, isFetching: assessmentFetching } = useReviewForCanonical(draftId)
  const promoteMutation = usePromoteDraft(draftId)

  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [assessmentStarted, setAssessmentStarted] = useState(false)

  useEffect(() => {
    if (draft && !assessmentStarted) {
      setAssessmentStarted(true)
      void fetchAssessment()
    }
  }, [draft, assessmentStarted, fetchAssessment])

  const handlePromote = () => {
    setShowConfirmDialog(false)
    promoteMutation.mutate(undefined, {
      onSuccess: (result) => {
        router.push(`/recipes/${result.canonicalRecipeId}`)
      },
    })
  }

  if (draftLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <Shield className="h-5 w-5 text-foreground" />
              <Skeleton className="h-5 w-48" />
            </div>
          </div>
        </div>
        <div className="mx-auto max-w-2xl px-4 py-8">
          <Card className="border-0 shadow-sm">
            <CardContent className="p-6 space-y-4">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <div className="space-y-3 mt-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full rounded-lg" />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  if (draftError) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-7 w-7 text-destructive" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load draft</h3>
        <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
          <RotateCcw className="h-4 w-4 mr-1" /> Retry
        </Button>
      </div>
    )
  }

  const d = (draft ?? {}) as Record<string, unknown>
  const draftTitle = (d.title as string) ?? "Untitled"
  const hasDescription = !!((d.description as string) ?? "").trim()
  const ingredientCount = ((d.ingredients as unknown[]) ?? []).length
  const stepCount = ((d.steps as unknown[]) ?? []).length
  const hasPrepTime = !!(d.prepTimeMinutes as number)
  const hasCookTime = !!(d.cookTimeMinutes as number)

  const a = (assessment ?? {}) as Record<string, unknown>
  const apiFindings = (a.findings ?? []) as Array<{ code: string; severity: "info" | "warning" | "error"; field: string; message: string }>
  const apiEligible = a.canonicalEligible as boolean | undefined
  const allowedActions = (a.allowedActions ?? []) as string[]

  const isEligible = apiEligible ?? false
  const status: AssessmentStatus = assessmentFetching ? "assessing" : (assessment ? (isEligible ? "eligible" : "not_eligible") : "assessing")

  const findings = apiFindings.length > 0
    ? apiFindings.map((f, i) => ({ id: `f-${i}`, severity: f.severity, field: f.field, message: f.message }))
    : []

  const infoFindings = findings.filter((f) => f.severity === "info")
  const warningFindings = findings.filter((f) => f.severity === "warning")
  const errorFindings = findings.filter((f) => f.severity === "error")

  const getSeverityIcon = (severity: string) => {
    if (severity === "error") return <AlertCircle className="h-4 w-4 text-destructive" />
    if (severity === "warning") return <AlertTriangle className="h-4 w-4 text-amber-500" />
    return <Check className="h-4 w-4 text-green-600" />
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Promotion Review</h1>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/drafts/${draftId}`}><ArrowLeft className="h-4 w-4 mr-1" />Back to draft</Link>
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-8">
        {status === "assessing" && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="mt-4 text-sm font-medium text-foreground">Checking eligibility...</p>
            <p className="mt-1 text-xs text-muted-foreground">Reviewing fields, ingredients, and steps</p>
          </div>
        )}

        {status !== "assessing" && (
          <div className="space-y-6">
            {/* Result Banner */}
            <Card className={`border-0 shadow-sm ${status === "eligible" ? "bg-green-50 dark:bg-green-950/20" : "bg-amber-50 dark:bg-amber-950/20"}`}>
              <CardContent className="p-6 text-center">
                <div className={`inline-flex h-12 w-12 items-center justify-center rounded-full ${status === "eligible" ? "bg-green-100 dark:bg-green-900/40" : "bg-amber-100 dark:bg-amber-900/40"}`}>
                  {status === "eligible"
                    ? <Check className="h-6 w-6 text-green-700 dark:text-green-400" />
                    : <AlertCircle className="h-6 w-6 text-amber-700 dark:text-amber-400" />}
                </div>
                <h2 className="mt-3 text-xl font-semibold text-foreground">
                  {status === "eligible" ? "Ready to become a trusted recipe" : "Not quite ready"}
                </h2>
                <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
                  {status === "eligible"
                    ? "All required fields are present. You can promote this draft to a trusted recipe in your collection."
                    : "Some issues need to be resolved before this draft can be promoted."}
                </p>
              </CardContent>
            </Card>

            {/* Field Summary */}
            <Card>
              <CardHeader><CardTitle className="text-base">Field summary</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">Title</span>
                    <Check className="h-4 w-4 text-green-600" />
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">Description</span>
                    {hasDescription ? <Check className="h-4 w-4 text-green-600" /> : <AlertCircle className="h-4 w-4 text-amber-500" />}
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">Ingredients</span>
                    <span className="text-foreground font-medium">{ingredientCount}</span>
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">Steps</span>
                    <span className="text-foreground font-medium">{stepCount}</span>
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">Prep time</span>
                    {hasPrepTime ? <Check className="h-4 w-4 text-green-600" /> : <span className="text-muted-foreground">—</span>}
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">Cook time</span>
                    {hasCookTime ? <Check className="h-4 w-4 text-green-600" /> : <span className="text-muted-foreground">—</span>}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Findings */}
            <Card>
              <CardHeader><CardTitle className="text-base">Findings</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {errorFindings.map((f) => (
                  <div key={f.id} className="flex items-start gap-3 rounded-lg bg-destructive/5 p-3">
                    {getSeverityIcon(f.severity)}<p className="text-sm text-foreground">{f.message}</p>
                  </div>
                ))}
                {warningFindings.map((f) => (
                  <div key={f.id} className="flex items-start gap-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 p-3">
                    {getSeverityIcon(f.severity)}<p className="text-sm text-foreground">{f.message}</p>
                  </div>
                ))}
                {infoFindings.map((f) => (
                  <div key={f.id} className="flex items-start gap-3 rounded-lg bg-muted/50 p-3">
                    {getSeverityIcon(f.severity)}<p className="text-sm text-muted-foreground">{f.message}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Actions */}
            <div className="flex items-center justify-between pt-4">
              <Button variant="outline" asChild>
                <Link href={`/drafts/${draftId}`}><ArrowLeft className="h-4 w-4 mr-1" />Continue editing</Link>
              </Button>
              {allowedActions.includes("promote") && (
                <Button onClick={() => setShowConfirmDialog(true)} disabled={promoteMutation.isPending}>
                  {promoteMutation.isPending
                    ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Promoting...</>
                    : <>Save as trusted recipe<ArrowRight className="h-4 w-4 ml-2" /></>}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Promote to trusted recipe?</AlertDialogTitle>
            <AlertDialogDescription>This will save the draft as a trusted recipe in your collection. The draft will be removed.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePromote}>Promote</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
