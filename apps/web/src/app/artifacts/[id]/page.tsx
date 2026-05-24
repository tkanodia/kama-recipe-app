"use client"

import { useState, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ShoppingCart,
  CalendarDays,
  FileStack,
  ArrowLeft,
  Pencil,
  Check,
  Archive,
  History,
  RotateCcw,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Save,
  X,
} from "lucide-react"
import {
  useArtifact,
  useUpdateArtifact,
  useArchiveArtifact,
  useArtifactRevisions,
  useRestoreArtifactRevision,
} from "@/hooks/use-artifacts"
import type {
  ShoppingListContent,
  ShoppingListCategory,
  ArtifactRevision,
} from "@kama/contracts"

const TYPE_ICONS: Record<string, typeof ShoppingCart> = {
  shopping_list: ShoppingCart,
  meal_plan: CalendarDays,
}

const TYPE_LABELS: Record<string, string> = {
  shopping_list: "Shopping List",
  meal_plan: "Meal Plan",
  pantry_feasibility: "Pantry Check",
}

function ShoppingListView({
  content,
  onContentChange,
}: {
  content: ShoppingListContent
  onContentChange?: (content: ShoppingListContent) => void
}) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set(),
  )

  const toggleCategory = (cat: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  const toggleItem = (catIdx: number, itemIdx: number) => {
    if (!onContentChange) return
    const updated: ShoppingListContent = {
      ...content,
      categories: content.categories.map((cat, ci) => {
        if (ci !== catIdx) return cat
        return {
          ...cat,
          items: cat.items.map((item, ii) => {
            if (ii !== itemIdx) return item
            return { ...item, checked: !item.checked }
          }),
        }
      }),
    }
    onContentChange(updated)
  }

  return (
    <div className="space-y-4">
      {content.categories.map((cat: ShoppingListCategory, catIdx: number) => {
        const isCollapsed = collapsedCategories.has(cat.category)
        const checkedCount = cat.items.filter((item) => item.checked).length

        return (
          <div key={cat.category} className="rounded-lg border border-border">
            <button
              className="flex w-full items-center justify-between px-4 py-3 text-left"
              onClick={() => toggleCategory(cat.category)}
            >
              <div className="flex items-center gap-2">
                {isCollapsed ? (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="font-medium text-foreground">
                  {cat.category}
                </span>
                <Badge variant="secondary" className="font-normal">
                  {checkedCount}/{cat.items.length}
                </Badge>
              </div>
            </button>

            {!isCollapsed && (
              <div className="border-t border-border">
                {cat.items.map((item, itemIdx) => {
                  const isChecked = !!item.checked
                  return (
                    <button
                      key={`${catIdx}-${itemIdx}`}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-muted/50 transition-colors"
                      onClick={() => toggleItem(catIdx, itemIdx)}
                    >
                      <div
                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                          isChecked
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground/30"
                        }`}
                      >
                        {isChecked && <Check className="h-2.5 w-2.5" />}
                      </div>
                      <span
                        className={`flex-1 text-sm ${
                          isChecked
                            ? "text-muted-foreground line-through"
                            : "text-foreground"
                        }`}
                      >
                        {item.quantity && (
                          <span className="font-medium">
                            {item.quantity}
                            {item.unit ? ` ${item.unit}` : ""}{" "}
                          </span>
                        )}
                        {item.text}
                      </span>
                      {item.recipeTitle && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {item.recipeTitle}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function GenericContentView({ content }: { content: Record<string, unknown> }) {
  return (
    <Card>
      <CardContent className="p-4">
        <pre className="overflow-x-auto whitespace-pre-wrap text-sm text-muted-foreground">
          {JSON.stringify(content, null, 2)}
        </pre>
      </CardContent>
    </Card>
  )
}

function RevisionsList({
  artifactId,
  onRestored,
}: {
  artifactId: string
  onRestored: () => void
}) {
  const { data, isLoading } = useArtifactRevisions(artifactId)
  const restoreRevision = useRestoreArtifactRevision(artifactId)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  const revisions = data?.items ?? []

  if (revisions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No revision history yet.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {revisions.map((rev: ArtifactRevision) => {
        const date = new Date(rev.createdAt)
        return (
          <div
            key={rev.id}
            className="flex items-center justify-between rounded-md border border-border px-4 py-3"
          >
            <div>
              <p className="text-sm font-medium text-foreground">
                {rev.changeSummary || "Revision"}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {date.toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}{" "}
                at{" "}
                {date.toLocaleTimeString(undefined, {
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={restoreRevision.isPending}
              onClick={() =>
                restoreRevision.mutate(rev.id, { onSuccess: onRestored })
              }
            >
              {restoreRevision.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <>
                  <RotateCcw className="h-3 w-3 mr-1" />
                  Restore
                </>
              )}
            </Button>
          </div>
        )
      })}
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center px-4">
          <Skeleton className="h-8 w-8 mr-3" />
          <Skeleton className="h-5 w-5 mr-3" />
          <Skeleton className="h-6 w-48" />
        </div>
      </div>
      <div className="mx-auto max-w-4xl px-4 py-6 space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full rounded-lg" />
        ))}
      </div>
    </div>
  )
}

export default function ArtifactDetailPage() {
  const params = useParams()
  const router = useRouter()
  const artifactId = params.id as string

  const { data: artifact, isLoading, isError, refetch } = useArtifact(artifactId)
  const updateArtifact = useUpdateArtifact(artifactId)
  const archiveArtifact = useArchiveArtifact()

  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState("")
  const [showRevisions, setShowRevisions] = useState(false)
  const [localContent, setLocalContent] = useState<ShoppingListContent | null>(
    null,
  )
  const [dirty, setDirty] = useState(false)

  const startEditTitle = useCallback(() => {
    setTitleDraft(artifact?.title ?? "")
    setEditingTitle(true)
  }, [artifact?.title])

  const saveTitle = () => {
    if (!titleDraft.trim()) {
      setEditingTitle(false)
      return
    }
    updateArtifact.mutate(
      { title: titleDraft.trim() },
      { onSuccess: () => setEditingTitle(false) },
    )
  }

  const handleArchive = () => {
    archiveArtifact.mutate(artifactId, {
      onSuccess: () => router.push("/artifacts"),
    })
  }

  const handleContentChange = (updated: ShoppingListContent) => {
    setLocalContent(updated)
    setDirty(true)
  }

  const handleSaveContent = () => {
    if (!localContent) return
    updateArtifact.mutate(
      { content: localContent },
      {
        onSuccess: () => {
          setDirty(false)
          setLocalContent(null)
        },
      },
    )
  }

  if (isLoading) return <DetailSkeleton />

  if (isError || !artifact) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center px-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push("/artifacts")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-7 w-7 text-destructive" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-foreground">
            {isError ? "Failed to load artifact" : "Artifact not found"}
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
    )
  }

  const Icon = TYPE_ICONS[artifact.artifactType] ?? FileStack
  const typeLabel = TYPE_LABELS[artifact.artifactType] ?? artifact.artifactType
  const isShoppingList = artifact.artifactType === "shopping_list"
  const shoppingContent = isShoppingList
    ? (localContent ??
      (artifact.content as ShoppingListContent))
    : null

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push("/artifacts")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Icon className="h-5 w-5 shrink-0 text-foreground" />
            {editingTitle ? (
              <div className="flex items-center gap-2">
                <Input
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  className="h-8 w-64"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveTitle()
                    if (e.key === "Escape") setEditingTitle(false)
                  }}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={saveTitle}
                  disabled={updateArtifact.isPending}
                >
                  {updateArtifact.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Check className="h-3 w-3" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setEditingTitle(false)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ) : (
              <button
                className="flex items-center gap-1.5 text-lg font-semibold text-foreground hover:text-foreground/80 truncate"
                onClick={startEditTitle}
              >
                <span className="truncate">{artifact.title}</span>
                <Pencil className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {dirty && (
              <Button
                size="sm"
                onClick={handleSaveContent}
                disabled={updateArtifact.isPending}
              >
                {updateArtifact.isPending ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <Save className="h-3 w-3 mr-1" />
                )}
                Save
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRevisions(!showRevisions)}
            >
              <History className="h-3 w-3 mr-1" />
              History
            </Button>
            {artifact.status === "active" && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleArchive}
                disabled={archiveArtifact.isPending}
              >
                {archiveArtifact.isPending ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <Archive className="h-3 w-3 mr-1" />
                )}
                Archive
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-4 flex items-center gap-2">
          <Badge variant="secondary" className="font-normal">
            {typeLabel}
          </Badge>
          {artifact.status === "archived" && (
            <Badge variant="outline" className="font-normal">
              <Archive className="h-3 w-3 mr-1" />
              Archived
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            Updated{" "}
            {new Date(artifact.updatedAt).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
        </div>

        {showRevisions && (
          <Card className="mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <History className="h-4 w-4" />
                Revision History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RevisionsList
                artifactId={artifactId}
                onRestored={() => {
                  setShowRevisions(false)
                  setLocalContent(null)
                  setDirty(false)
                }}
              />
            </CardContent>
          </Card>
        )}

        {isShoppingList && shoppingContent ? (
          <ShoppingListView
            content={shoppingContent}
            onContentChange={handleContentChange}
          />
        ) : (
          <GenericContentView
            content={artifact.content as Record<string, unknown>}
          />
        )}
      </div>
    </div>
  )
}
