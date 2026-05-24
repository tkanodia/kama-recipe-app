"use client"

import { useState, useMemo, useCallback } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Refrigerator,
  Search,
  X,
  Plus,
  ChefHat,
  Loader2,
  AlertCircle,
  RotateCcw,
  ClipboardPaste,
} from "lucide-react"
import {
  usePantryItems,
  useAddPantry,
  useAddPantryFromText,
  useRemovePantry,
} from "@/hooks/use-pantry"
import { useIngredientSearch } from "@/hooks/use-ingredients"
import { useDebounce } from "@/hooks/use-debounce"
import { EmptyState } from "@/components/empty-state"
import type { PantryItem, IngredientSearchItem } from "@kama/contracts"

function PantrySkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-full" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-5 w-32" />
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="h-8 w-24 rounded-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PantryPage() {
  const [ingredientSearch, setIngredientSearch] = useState("")
  const [textInput, setTextInput] = useState("")
  const [showTextInput, setShowTextInput] = useState(false)
  const [textResult, setTextResult] = useState<{
    notFound: string[]
    suggestions: Array<{
      text: string
      suggestedIngredients: Array<{ id: string; name: string }>
    }>
  } | null>(null)

  const debouncedSearch = useDebounce(ingredientSearch, 300)

  const { data, isLoading, isError, refetch } = usePantryItems()
  const { data: searchData, isLoading: searchLoading } =
    useIngredientSearch(debouncedSearch, 10)

  const addPantry = useAddPantry()
  const addFromText = useAddPantryFromText()
  const removePantry = useRemovePantry()

  const items = data?.items ?? []
  const searchResults = searchData?.items ?? []

  const pantryIngredientIds = useMemo(
    () => new Set(items.map((i) => i.ingredientId)),
    [items],
  )

  const grouped = useMemo(() => {
    const map = new Map<string, PantryItem[]>()
    for (const item of items) {
      const cat = item.category || "Other"
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat)!.push(item)
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [items])

  const handleAddIngredient = useCallback(
    (ingredient: IngredientSearchItem) => {
      addPantry.mutate({ ingredientIds: [ingredient.id] })
      setIngredientSearch("")
    },
    [addPantry],
  )

  const handleAddFromText = useCallback(() => {
    if (!textInput.trim()) return
    addFromText.mutate(
      { text: textInput.trim() },
      {
        onSuccess: (result) => {
          setTextInput("")
          if (result.notFound.length > 0 || result.suggestions.length > 0) {
            setTextResult({
              notFound: result.notFound,
              suggestions: result.suggestions,
            })
          } else {
            setTextResult(null)
          }
        },
      },
    )
  }, [textInput, addFromText])

  const handleRemoveItem = useCallback(
    (pantryItemId: string) => {
      removePantry.mutate([pantryItemId])
    },
    [removePantry],
  )

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center px-4">
            <div className="flex items-center gap-3">
              <Refrigerator className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">
                My Pantry
              </h1>
            </div>
          </div>
        </div>
        <div className="mx-auto max-w-4xl px-4 py-6">
          <PantrySkeleton />
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
              <Refrigerator className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">
                My Pantry
              </h1>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-7 w-7 text-destructive" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-foreground">
            Failed to load pantry
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
            <Refrigerator className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">
              My Pantry
            </h1>
            {items.length > 0 && (
              <Badge variant="secondary" className="font-normal">
                {items.length}
              </Badge>
            )}
          </div>
          {items.length > 0 && (
            <Button asChild>
              <Link href="/pantry/feasibility">
                <ChefHat className="h-4 w-4 mr-1" />
                What can I cook?
              </Link>
            </Button>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6 space-y-6">
        {/* Add by ingredient search */}
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={ingredientSearch}
              onChange={(e) => setIngredientSearch(e.target.value)}
              placeholder="Search ingredients to add..."
              className="pl-9"
            />
          </div>

          {debouncedSearch.length >= 2 && (
            <Card className="border border-border">
              <CardContent className="p-0">
                {searchLoading && (
                  <div className="flex items-center justify-center py-6">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                )}
                {!searchLoading && searchResults.length === 0 && (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    No ingredients found for &ldquo;{debouncedSearch}&rdquo;
                  </p>
                )}
                {!searchLoading &&
                  searchResults.map((ingredient) => {
                    const alreadyAdded = pantryIngredientIds.has(ingredient.id)
                    return (
                      <button
                        key={ingredient.id}
                        className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-muted/50 transition-colors disabled:opacity-50"
                        disabled={alreadyAdded || addPantry.isPending}
                        onClick={() => handleAddIngredient(ingredient)}
                      >
                        <span className="text-sm text-foreground">
                          {ingredient.name}
                        </span>
                        {alreadyAdded ? (
                          <Badge
                            variant="secondary"
                            className="text-xs font-normal"
                          >
                            In pantry
                          </Badge>
                        ) : (
                          <Plus className="h-4 w-4 text-muted-foreground" />
                        )}
                      </button>
                    )
                  })}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Toggle for text input */}
        <div>
          <button
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowTextInput(!showTextInput)}
          >
            <ClipboardPaste className="h-4 w-4" />
            {showTextInput ? "Hide" : "Paste a list of ingredients"}
          </button>

          {showTextInput && (
            <div className="mt-3 space-y-3">
              <Textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Paste your ingredient list here, e.g.&#10;chicken breast&#10;olive oil&#10;garlic&#10;tomatoes"
                rows={5}
              />
              <Button
                onClick={handleAddFromText}
                disabled={!textInput.trim() || addFromText.isPending}
              >
                {addFromText.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4 mr-1" />
                    Add from text
                  </>
                )}
              </Button>

              {addFromText.isError && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  Failed to add ingredients. Please try again.
                </div>
              )}

              {textResult && (
                <Card className="border border-border">
                  <CardContent className="p-4 space-y-3">
                    {textResult.notFound.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          Not recognized:
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {textResult.notFound.map((text) => (
                            <Badge
                              key={text}
                              variant="outline"
                              className="font-normal text-xs"
                            >
                              {text}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {textResult.suggestions.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          Did you mean:
                        </p>
                        <div className="mt-1 space-y-1">
                          {textResult.suggestions.map((s) => (
                            <div
                              key={s.text}
                              className="flex items-center gap-2 text-sm"
                            >
                              <span className="text-muted-foreground">
                                &ldquo;{s.text}&rdquo; →
                              </span>
                              {s.suggestedIngredients.map((ing) => (
                                <Button
                                  key={ing.id}
                                  variant="outline"
                                  size="sm"
                                  className="h-7 text-xs"
                                  disabled={pantryIngredientIds.has(ing.id)}
                                  onClick={() =>
                                    addPantry.mutate({
                                      ingredientIds: [ing.id],
                                    })
                                  }
                                >
                                  <Plus className="h-3 w-3 mr-1" />
                                  {ing.name}
                                </Button>
                              ))}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setTextResult(null)}
                    >
                      Dismiss
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>

        {/* Pantry items grouped by category */}
        {items.length === 0 ? (
          <EmptyState
            icon={Refrigerator}
            title="Your pantry is empty"
            description="Add ingredients above to track what you have on hand, then check what you can cook."
          />
        ) : (
          <div className="space-y-6">
            {grouped.map(([category, categoryItems]) => (
              <div key={category}>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">
                  {category}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {categoryItems.map((item) => (
                    <Badge
                      key={item.id}
                      variant="secondary"
                      className="gap-1.5 pr-1.5 py-1.5 text-sm font-normal"
                    >
                      {item.ingredientName}
                      <button
                        className="ml-0.5 rounded-full p-0.5 hover:bg-foreground/10 transition-colors"
                        onClick={() => handleRemoveItem(item.id)}
                        disabled={removePantry.isPending}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            ))}

            <div className="pt-4 border-t border-border">
              <Button asChild size="lg" className="w-full sm:w-auto">
                <Link href="/pantry/feasibility">
                  <ChefHat className="h-4 w-4 mr-2" />
                  What can I cook?
                </Link>
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
