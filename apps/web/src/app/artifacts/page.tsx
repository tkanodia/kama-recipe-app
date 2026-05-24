"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  ShoppingCart,
  CalendarDays,
  FileStack,
  Plus,
  AlertCircle,
  RotateCcw,
  Loader2,
  Archive,
} from "lucide-react"
import { useArtifactsList } from "@/hooks/use-artifacts"
import { EmptyState } from "@/components/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import type { Artifact } from "@kama/contracts"

type TypeFilter = "all" | "shopping_list" | "meal_plan"
type StatusFilter = "active" | "archived"

const TYPE_ICONS: Record<string, typeof ShoppingCart> = {
  shopping_list: ShoppingCart,
  meal_plan: CalendarDays,
}

const TYPE_LABELS: Record<string, string> = {
  shopping_list: "Shopping List",
  meal_plan: "Meal Plan",
  pantry_feasibility: "Pantry Check",
}

function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const Icon = TYPE_ICONS[artifact.artifactType] ?? FileStack
  const typeLabel = TYPE_LABELS[artifact.artifactType] ?? artifact.artifactType
  const date = new Date(artifact.updatedAt)
  const formattedDate = date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })

  return (
    <Card className="group border border-border hover:border-foreground/20 transition-colors">
      <Link href={`/artifacts/${artifact.id}`}>
        <CardContent className="p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
              <Icon className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold text-foreground line-clamp-1 group-hover:underline">
                {artifact.title}
              </h3>
              <div className="mt-1.5 flex items-center gap-2">
                <Badge variant="secondary" className="font-normal text-xs">
                  {typeLabel}
                </Badge>
                {artifact.status === "archived" && (
                  <Badge variant="outline" className="font-normal text-xs">
                    <Archive className="h-3 w-3 mr-1" />
                    Archived
                  </Badge>
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Updated {formattedDate}
              </p>
            </div>
          </div>
        </CardContent>
      </Link>
    </Card>
  )
}

function ArtifactsGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="border border-border">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-3 w-28" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default function ArtifactsPage() {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active")

  const listParams = useMemo(() => {
    const p: { type?: string; status?: string } = {}
    if (typeFilter !== "all") p.type = typeFilter
    p.status = statusFilter
    return p
  }, [typeFilter, statusFilter])

  const { data, isLoading, isError, refetch } = useArtifactsList(listParams)

  const artifacts = data?.items ?? []

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <FileStack className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">
              Artifacts
            </h1>
            {data && (
              <Badge variant="secondary" className="font-normal">
                {data.total}
              </Badge>
            )}
          </div>
          <Button asChild>
            <Link href="/create/shopping-list/new">
              <Plus className="h-4 w-4 mr-1" />
              Shopping List
            </Link>
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex rounded-lg border border-border p-0.5">
            {(["all", "shopping_list", "meal_plan"] as TypeFilter[]).map(
              (t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`rounded-md px-3 py-1 text-sm transition-colors ${
                    typeFilter === t
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t === "all"
                    ? "All"
                    : t === "shopping_list"
                      ? "Shopping Lists"
                      : "Meal Plans"}
                </button>
              ),
            )}
          </div>

          <div className="h-5 w-px bg-border" />

          <div className="flex rounded-lg border border-border p-0.5">
            {(["active", "archived"] as StatusFilter[]).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`rounded-md px-3 py-1 text-sm transition-colors ${
                  statusFilter === s
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {s === "active" ? "Active" : "Archived"}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6">
          {isLoading ? (
            <ArtifactsGridSkeleton />
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
                <AlertCircle className="h-7 w-7 text-destructive" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-foreground">
                Failed to load artifacts
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
          ) : artifacts.length === 0 ? (
            <EmptyState
              icon={FileStack}
              title="No artifacts yet"
              description={
                statusFilter === "archived"
                  ? "You haven't archived any artifacts."
                  : "Create a shopping list or meal plan to get started."
              }
              action={
                statusFilter === "active"
                  ? {
                      label: "Create Shopping List",
                      href: "/create/shopping-list/new",
                      icon: Plus,
                    }
                  : undefined
              }
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {artifacts.map((artifact) => (
                <ArtifactCard key={artifact.id} artifact={artifact} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
