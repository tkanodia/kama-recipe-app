"use client"

import { useState, useMemo, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  CalendarDays,
  ArrowLeft,
  Search,
  Check,
  X,
  Loader2,
  AlertCircle,
  ChevronRight,
} from "lucide-react"
import { useSearch } from "@/hooks/use-search"
import { useDebounce } from "@/hooks/use-debounce"
import { useGenerateArtifact } from "@/hooks/use-artifacts"
import type { Artifact, MealPlanContent } from "@kama/contracts"

type Step = "configure" | "result"

export default function NewMealPlanPage() {
  const router = useRouter()

  const [step, setStep] = useState<Step>("configure")
  const [days, setDays] = useState(7)
  const [mealsPerDay, setMealsPerDay] = useState(3)
  const [title, setTitle] = useState("")
  const [instructions, setInstructions] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRecipes, setSelectedRecipes] = useState<
    Map<string, { id: string; title: string }>
  >(new Map())
  const [artifact, setArtifact] = useState<Artifact | null>(null)

  const debouncedQuery = useDebounce(searchQuery, 300)
  const generateArtifact = useGenerateArtifact()

  const {
    data: searchData,
    isLoading: searchLoading,
  } = useSearch(debouncedQuery, undefined, {
    enabled: !!debouncedQuery && step === "configure",
  })

  const searchResults = useMemo(
    () => searchData?.pages.flatMap((p) => p.items) ?? [],
    [searchData],
  )

  const toggleRecipe = useCallback((id: string, recipeTitle: string) => {
    setSelectedRecipes((prev) => {
      const next = new Map(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.set(id, { id, title: recipeTitle })
      }
      return next
    })
  }, [])

  const handleGenerate = () => {
    const recipeIds = Array.from(selectedRecipes.keys())
    generateArtifact.mutate(
      {
        artifactType: "meal_plan",
        days,
        mealsPerDay,
        recipeIds: recipeIds.length > 0 ? recipeIds : undefined,
        instructions: instructions.trim() || undefined,
        title: title.trim() || undefined,
      },
      {
        onSuccess: (data) => {
          setArtifact(data)
          setStep("result")
        },
      },
    )
  }

  const content = artifact?.content as MealPlanContent | undefined

  if (step === "result" && artifact && content) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setStep("configure")}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <CalendarDays className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">
                {artifact.title}
              </h1>
            </div>
            <Button asChild>
              <Link href={`/artifacts/${artifact.id}`}>
                View in Artifacts
                <ChevronRight className="h-4 w-4 ml-1" />
              </Link>
            </Button>
          </div>
        </div>

        <div className="mx-auto max-w-4xl px-4 py-6 space-y-6">
          {content.days.map((day) => (
            <div key={day.day} className="space-y-3">
              <h2 className="text-base font-semibold text-foreground">
                {day.label}
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {day.slots.map((slot, slotIdx) => (
                  <Card
                    key={slotIdx}
                    className="border border-border hover:border-foreground/20 transition-colors"
                  >
                    <CardContent className="p-4 space-y-2">
                      <Badge variant="secondary" className="text-xs font-normal">
                        {slot.meal}
                      </Badge>
                      {slot.recipeId ? (
                        <Link
                          href={`/recipes/${slot.recipeId}`}
                          className="block font-medium text-foreground hover:underline line-clamp-2"
                        >
                          {slot.recipeTitle}
                        </Link>
                      ) : (
                        <p className="font-medium text-foreground line-clamp-2">
                          {slot.recipeTitle ?? "Open slot"}
                        </p>
                      )}
                      {slot.notes && (
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {slot.notes}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

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
            <CalendarDays className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">
              New Meal Plan
            </h1>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6 space-y-8">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="days">Number of days</Label>
            <Select
              value={String(days)}
              onValueChange={(v) => setDays(Number(v))}
            >
              <SelectTrigger id="days">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 14 }, (_, i) => i + 1).map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} {n === 1 ? "day" : "days"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="meals">Meals per day</Label>
            <Select
              value={String(mealsPerDay)}
              onValueChange={(v) => setMealsPerDay(Number(v))}
            >
              <SelectTrigger id="meals">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} {n === 1 ? "meal" : "meals"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="title">Title (optional)</Label>
          <Input
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Weeknight dinners for the family"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="instructions">
            Dietary preferences / constraints (optional)
          </Label>
          <Textarea
            id="instructions"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="e.g. No dairy, high protein, kid-friendly"
            rows={3}
          />
        </div>

        <div className="space-y-4">
          <div>
            <Label>Include specific recipes (optional)</Label>
            <p className="mt-1 text-sm text-muted-foreground">
              Pick recipes you&apos;d like included in the meal plan.
            </p>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search your recipes..."
              className="pl-9"
            />
          </div>

          {selectedRecipes.size > 0 && (
            <div className="flex flex-wrap gap-2">
              {Array.from(selectedRecipes.values()).map((r) => (
                <Badge
                  key={r.id}
                  variant="default"
                  className="cursor-pointer gap-1 pr-1.5"
                  onClick={() => toggleRecipe(r.id, r.title)}
                >
                  {r.title}
                  <X className="h-3 w-3" />
                </Badge>
              ))}
            </div>
          )}

          {debouncedQuery && (
            <div className="space-y-1">
              {searchLoading && (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              )}
              {!searchLoading && searchResults.length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  No recipes found for &ldquo;{debouncedQuery}&rdquo;
                </p>
              )}
              {!searchLoading &&
                searchResults.map((result) => {
                  const isSelected = selectedRecipes.has(result.id)
                  return (
                    <Card
                      key={result.id}
                      className={`cursor-pointer border transition-colors ${
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-foreground/20"
                      }`}
                      onClick={() => toggleRecipe(result.id, result.title)}
                    >
                      <CardContent className="flex items-center gap-3 p-3">
                        <div
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                            isSelected
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-muted-foreground/30"
                          }`}
                        >
                          {isSelected && <Check className="h-3 w-3" />}
                        </div>
                        <p className="text-sm font-medium text-foreground line-clamp-1">
                          {result.title}
                        </p>
                      </CardContent>
                    </Card>
                  )
                })}
            </div>
          )}
        </div>

        <div className="sticky bottom-0 border-t border-border bg-background py-4">
          <Button
            className="w-full"
            size="lg"
            disabled={generateArtifact.isPending}
            onClick={handleGenerate}
          >
            {generateArtifact.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <CalendarDays className="h-4 w-4 mr-2" />
                Generate Meal Plan
              </>
            )}
          </Button>
          {generateArtifact.isError && (
            <div className="mt-3 flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              Failed to generate meal plan. Please try again.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
