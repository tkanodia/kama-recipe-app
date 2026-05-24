"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
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
  History,
  RotateCcw,
  Loader2,
  Clock,
  FileText,
} from "lucide-react"
import { useRecipeRevisions, useRestoreRevision } from "@/hooks/use-recipes"

interface RevisionHistoryDrawerProps {
  recipeId: string
  trigger?: React.ReactNode
}

export default function RevisionHistoryDrawer({
  recipeId,
  trigger,
}: RevisionHistoryDrawerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [restoreTarget, setRestoreTarget] = useState<string | null>(null)

  const { data: revisionsData, isLoading } = useRecipeRevisions(recipeId)
  const restoreMutation = useRestoreRevision(recipeId)

  const revisions = revisionsData?.items ?? []

  const handleRestore = async () => {
    if (!restoreTarget) return
    restoreMutation.mutate(restoreTarget, {
      onSuccess: () => {
        setRestoreTarget(null)
        setIsOpen(false)
      },
    })
  }

  return (
    <>
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetTrigger asChild>
          {trigger || (
            <button className="flex w-full items-center gap-2 text-sm">
              <History className="h-4 w-4" />
              View Revisions
            </button>
          )}
        </SheetTrigger>
        <SheetContent className="w-full sm:max-w-md">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Revision History
            </SheetTitle>
          </SheetHeader>

          <div className="mt-6">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <p className="mt-3 text-sm text-muted-foreground">Loading revisions...</p>
              </div>
            ) : revisions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                  <FileText className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="mt-3 text-sm font-medium text-foreground">No previous versions</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Revisions are created when you edit ingredients, steps, title, times, or servings.
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {revisions.map((revision) => (
                  <div key={revision.id} className="rounded-lg border border-border p-4 hover:bg-muted/50 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span className="text-xs text-muted-foreground">
                            {new Date(revision.createdAt).toLocaleString()}
                          </span>
                        </div>
                        {revision.changeSummary && (
                          <p className="mt-2 text-sm text-foreground leading-relaxed">
                            {revision.changeSummary}
                          </p>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRestoreTarget(revision.id)}
                        className="shrink-0"
                      >
                        <RotateCcw className="h-3.5 w-3.5 mr-1" />
                        Restore
                      </Button>
                    </div>
                  </div>
                ))}

                <p className="pt-4 text-center text-xs text-muted-foreground">
                  Restoring a version saves your current recipe as a new revision before applying the restored content.
                </p>
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>

      <AlertDialog open={restoreTarget !== null} onOpenChange={(open) => { if (!open) setRestoreTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Restore this version?</AlertDialogTitle>
            <AlertDialogDescription>
              Your current recipe will be saved as a new revision before the restored version is applied. Nothing is lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={restoreMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRestore} disabled={restoreMutation.isPending}>
              {restoreMutation.isPending ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Restoring...</>
              ) : "Restore"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
