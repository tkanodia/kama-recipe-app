"use client"

import { useMemo } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ChefHat,
  ArrowLeft,
  AlertCircle,
  RotateCcw,
  Loader2,
  ShoppingCart,
  CheckCircle2,
  Clock,
  XCircle,
  ExternalLink,
} from "lucide-react"
import { useFeasibility } from "@/hooks/use-pantry"
import { useGenerateArtifact } from "@/hooks/use-artifacts"
import { EmptyState } from "@/components/empty-state"
import type { FeasibilityRecipe } from "@kama/contracts"

function FeasibilitySkeleton() {
  return (
    <div className="space-y-8">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-3">
          <Skeleton className="h-6 w-48" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {Array.from({ length: 2 }).map((_, j) => (
              <Skeleton key={j} className="h-32 rounded-lg" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    pct >= 80
      ? "bg-green-500"
      : pct >= 50
        ? "bg-yellow-500"
        : "bg-muted-foreground/30"

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-muted">
        <div
          className={`h-2 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-muted-foreground w-10 text-right">
        {pct}%
      </span>
    </div>
  )
}

function RecipeCard({ recipe }: { recipe: FeasibilityRecipe }) {
  return (
    <Card className="border border-border hover:border-foreground/20 transition-colors">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <Link
            href={`/recipes/${recipe.recipeId}`}
            className="font-semibold text-foreground hover:underline line-clamp-1"
          >
            {recipe.recipeTitle}
          </Link>
          <Link href={`/recipes/${recipe.recipeId}`}>
            <ExternalLink className="h-4 w-4 text-muted-foreground shrink-0" />
          </Link>
        </div>

        <ScoreBar score={recipe.feasibilityScore} />

        <p className="text-xs text-muted-foreground">
          {recipe.matchedIngredients} of {recipe.totalIngredients} ingredients
        </p>

        {recipe.missingIngredients.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {[...new Set(recipe.missingIngredients)].map((name) => (
              <Badge
                key={name}
                variant="outline"
                className="text-xs font-normal"
              >
                {name}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

type SectionProps = {
  title: string
  icon: typeof CheckCircle2
  accent: string
  recipes: FeasibilityRecipe[]
}

function FeasibilitySection({ title, icon: Icon, accent, recipes }: SectionProps) {
  if (recipes.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`h-5 w-5 ${accent}`} />
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <Badge variant="secondary" className="font-normal">
          {recipes.length}
        </Badge>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {recipes.map((r) => (
          <RecipeCard key={r.recipeId} recipe={r} />
        ))}
      </div>
    </div>
  )
}

export default function FeasibilityPage() {
  const router = useRouter()
  const { data, isLoading, isError, refetch } = useFeasibility()
  const generateArtifact = useGenerateArtifact()

  const totalRecipes = useMemo(() => {
    if (!data) return 0
    return (
      data.fullyFeasible.length +
      data.partiallyFeasible.length +
      data.notFeasible.length
    )
  }, [data])

  const missingFromPartial = useMemo(() => {
    if (!data) return []
    const all = new Set<string>()
    for (const r of data.partiallyFeasible) {
      for (const name of r.missingIngredients) {
        all.add(name)
      }
    }
    return Array.from(all)
  }, [data])

  const handleSaveCheck = () => {
    generateArtifact.mutate(
      {
        artifactType: "pantry_feasibility",
        title: `Pantry Check – ${new Date().toLocaleDateString()}`,
      },
      {
        onSuccess: (artifact) => {
          router.push(`/artifacts/${artifact.id}`)
        },
      },
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center px-4">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => router.back()}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <ChefHat className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">
                What Can I Cook?
              </h1>
            </div>
          </div>
        </div>
        <div className="mx-auto max-w-4xl px-4 py-6">
          <FeasibilitySkeleton />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center px-4">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => router.back()}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <ChefHat className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">
                What Can I Cook?
              </h1>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-7 w-7 text-destructive" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-foreground">
            Failed to check feasibility
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

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.back()}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <ChefHat className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">
              What Can I Cook?
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveCheck}
              disabled={generateArtifact.isPending}
            >
              {generateArtifact.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save this check"
              )}
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6 space-y-8">
        {totalRecipes === 0 ? (
          <EmptyState
            icon={ChefHat}
            title="No recipes to check"
            description="Add some recipes and pantry items first to see what you can cook."
            action={{
              label: "Go to Pantry",
              href: "/pantry",
            }}
          />
        ) : (
          <>
            <FeasibilitySection
              title="Ready to cook"
              icon={CheckCircle2}
              accent="text-green-500"
              recipes={data!.fullyFeasible}
            />

            <FeasibilitySection
              title="Almost there"
              icon={Clock}
              accent="text-yellow-500"
              recipes={data!.partiallyFeasible}
            />

            {data!.partiallyFeasible.length > 0 &&
              missingFromPartial.length > 0 && (
                <div className="rounded-lg border border-border bg-muted/30 p-4">
                  <p className="text-sm font-medium text-foreground mb-2">
                    Missing ingredients for &ldquo;Almost there&rdquo; recipes:
                  </p>
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {missingFromPartial.map((name) => (
                      <Badge
                        key={name}
                        variant="outline"
                        className="text-xs font-normal"
                      >
                        {name}
                      </Badge>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/create/shopping-list/new?recipes=${data!.partiallyFeasible.map((r) => r.recipeId).join(",")}`}>
                      <ShoppingCart className="h-4 w-4 mr-1" />
                      Make shopping list for missing
                    </Link>
                  </Button>
                </div>
              )}

            <FeasibilitySection
              title="Need more ingredients"
              icon={XCircle}
              accent="text-muted-foreground"
              recipes={data!.notFeasible}
            />
          </>
        )}
      </div>
    </div>
  )
}
