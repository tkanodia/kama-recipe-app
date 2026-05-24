"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ShoppingCart,
  CalendarDays,
  ChefHat,
  Sparkles,
  FileStack,
  ChevronRight,
} from "lucide-react"
import { useArtifactsList } from "@/hooks/use-artifacts"
import type { Artifact } from "@kama/contracts"

const TYPE_ICONS: Record<string, typeof ShoppingCart> = {
  shopping_list: ShoppingCart,
  meal_plan: CalendarDays,
  pantry_feasibility: ChefHat,
}

const TYPE_LABELS: Record<string, string> = {
  shopping_list: "Shopping List",
  meal_plan: "Meal Plan",
  pantry_feasibility: "Pantry Check",
}

const actions = [
  {
    title: "Shopping List",
    description: "Build a shopping list from your recipes",
    icon: ShoppingCart,
    href: "/create/shopping-list/new",
  },
  {
    title: "Meal Plan",
    description: "Plan your meals for the week",
    icon: CalendarDays,
    href: "/create/meal-plan/new",
  },
  {
    title: "What Can I Cook?",
    description: "Check what you can make with what you have",
    icon: ChefHat,
    href: "/pantry/feasibility",
  },
] as const

function RecentArtifactRow({ artifact }: { artifact: Artifact }) {
  const Icon = TYPE_ICONS[artifact.artifactType] ?? FileStack
  const label = TYPE_LABELS[artifact.artifactType] ?? artifact.artifactType
  const date = new Date(artifact.updatedAt)
  const formattedDate = date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })

  return (
    <Link
      href={`/artifacts/${artifact.id}`}
      className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-muted/50 transition-colors"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground line-clamp-1">
          {artifact.title}
        </p>
        <p className="text-xs text-muted-foreground">
          {label} · {formattedDate}
        </p>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
    </Link>
  )
}

function RecentSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-2.5">
          <Skeleton className="h-9 w-9 rounded-lg" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function CreateHubPage() {
  const { data, isLoading } = useArtifactsList({ status: "active" })

  const recentArtifacts = (data?.items ?? []).slice(0, 5)

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center px-4">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Create</h1>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6 space-y-10">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {actions.map((action) => {
            const Icon = action.icon
            return (
              <Card
                key={action.href}
                className="group border border-border hover:border-foreground/20 transition-colors"
              >
                <Link href={action.href}>
                  <CardContent className="p-6 space-y-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted group-hover:bg-foreground/5 transition-colors">
                      <Icon className="h-6 w-6 text-foreground" />
                    </div>
                    <h3 className="font-semibold text-foreground group-hover:underline">
                      {action.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {action.description}
                    </p>
                  </CardContent>
                </Link>
              </Card>
            )
          })}
        </div>

        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-foreground">
              Recent artifacts
            </h2>
            {recentArtifacts.length > 0 && (
              <Button variant="ghost" size="sm" asChild>
                <Link href="/artifacts">
                  View all
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Link>
              </Button>
            )}
          </div>

          {isLoading ? (
            <RecentSkeleton />
          ) : recentArtifacts.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border py-10 text-center">
              <FileStack className="mx-auto h-10 w-10 text-muted-foreground/30" />
              <p className="mt-3 text-sm text-muted-foreground">
                No artifacts yet. Create a shopping list or meal plan to get
                started.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border divide-y divide-border">
              {recentArtifacts.map((artifact) => (
                <RecentArtifactRow key={artifact.id} artifact={artifact} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
