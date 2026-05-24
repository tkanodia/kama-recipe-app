"use client"

import { useState, useMemo, useCallback, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Search,
  ShoppingCart,
  Loader2,
  Check,
  ChevronDown,
  ChevronRight,
  ArrowLeft,
  Pencil,
  Save,
  X,
  AlertCircle,
} from "lucide-react"
import { useSearch } from "@/hooks/use-search"
import { useDebounce } from "@/hooks/use-debounce"
import { useGenerateArtifact, useUpdateArtifact } from "@/hooks/use-artifacts"
import type { Artifact, ShoppingListContent } from "@kama/contracts"

type Step = "select" | "review"

export default function NewShoppingListPage() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [step, setStep] = useState<Step>("select")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRecipes, setSelectedRecipes] = useState<
    Map<string, { id: string; title: string }>
  >(new Map())
  const [preloaded, setPreloaded] = useState(false)

  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set())
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set(),
  )
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState("")

  const debouncedQuery = useDebounce(searchQuery, 300)
  const generateArtifact = useGenerateArtifact()

  const {
    data: searchData,
    isLoading: searchLoading,
  } = useSearch(debouncedQuery, undefined, {
    enabled: !!debouncedQuery && step === "select",
  })

  const searchResults = useMemo(
    () => searchData?.pages.flatMap((p) => p.items) ?? [],
    [searchData],
  )

  useEffect(() => {
    if (preloaded) return
    const recipesParam = searchParams.get("recipes")
    if (!recipesParam) {
      setPreloaded(true)
      return
    }
    const ids = recipesParam.split(",").filter(Boolean)
    if (ids.length > 0) {
      const map = new Map<string, { id: string; title: string }>()
      for (const id of ids) {
        map.set(id, { id, title: id })
      }
      setSelectedRecipes(map)
    }
    setPreloaded(true)
  }, [searchParams, preloaded])

  const toggleRecipe = useCallback(
    (id: string, title: string) => {
      setSelectedRecipes((prev) => {
        const next = new Map(prev)
        if (next.has(id)) {
          next.delete(id)
        } else {
          next.set(id, { id, title })
        }
        return next
      })
    },
    [],
  )

  const handleGenerate = () => {
    const recipeIds = Array.from(selectedRecipes.keys())
    generateArtifact.mutate(
      { artifactType: "shopping_list", recipeIds },
      {
        onSuccess: (data) => {
          setArtifact(data)
          setTitleDraft(data.title)
          setStep("review")
        },
      },
    )
  }

  const itemKey = (catIdx: number, itemIdx: number) =>
    `${catIdx}-${itemIdx}`

  const toggleItem = (key: string) => {
    setCheckedItems((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleCategory = (cat: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  const content = artifact?.content as ShoppingListContent | undefined

  const updateArtifact = useUpdateArtifact(artifact?.id ?? "")

  const handleSave = () => {
    if (!artifact || !content) return

    const updatedContent: ShoppingListContent = {
      ...content,
      categories: content.categories.map((cat, catIdx) => ({
        ...cat,
        items: cat.items.map((item, itemIdx) => ({
          ...item,
          checked: checkedItems.has(itemKey(catIdx, itemIdx)),
        })),
      })),
    }

    updateArtifact.mutate(
      {
        title: titleDraft || artifact.title,
        content: updatedContent,
      },
      {
        onSuccess: (updated) => {
          router.push(`/artifacts/${updated.id}`)
        },
      },
    )
  }

  if (step === "select") {
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
              <ShoppingCart className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">
                New Shopping List
              </h1>
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-4xl px-4 py-6 space-y-6">
          <div>
            <h2 className="text-base font-medium text-foreground">
              Select recipes
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose recipes to generate a combined shopping list.
            </p>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search your recipes..."
              className="pl-9"
              autoFocus
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

          <div className="space-y-2">
            {searchLoading && debouncedQuery && (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}

            {!searchLoading && debouncedQuery && searchResults.length === 0 && (
              <div className="flex flex-col items-center py-10 text-center">
                <Search className="h-10 w-10 text-muted-foreground/30" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No recipes found for &ldquo;{debouncedQuery}&rdquo;
                </p>
              </div>
            )}

            {searchResults.map((result) => {
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
                  <CardContent className="flex items-center gap-3 p-4">
                    <div
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                        isSelected
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground/30"
                      }`}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-foreground line-clamp-1">
                        {result.title}
                      </p>
                      {result.description && (
                        <p className="mt-0.5 text-sm text-muted-foreground line-clamp-1">
                          {result.description}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )
            })}

            {!debouncedQuery && (
              <div className="flex flex-col items-center py-10 text-center">
                <Search className="h-10 w-10 text-muted-foreground/30" />
                <p className="mt-3 text-sm text-muted-foreground">
                  Search for recipes to add to your shopping list.
                </p>
              </div>
            )}
          </div>

          <div className="sticky bottom-0 border-t border-border bg-background py-4">
            <Button
              className="w-full"
              size="lg"
              disabled={
                selectedRecipes.size === 0 || generateArtifact.isPending
              }
              onClick={handleGenerate}
            >
              {generateArtifact.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <ShoppingCart className="h-4 w-4 mr-2" />
                  Generate Shopping List ({selectedRecipes.size}{" "}
                  {selectedRecipes.size === 1 ? "recipe" : "recipes"})
                </>
              )}
            </Button>
            {generateArtifact.isError && (
              <div className="mt-3 flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                Failed to generate shopping list. Please try again.
              </div>
            )}
          </div>
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
              onClick={() => setStep("select")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <ShoppingCart className="h-5 w-5 text-foreground" />
            {editingTitle ? (
              <div className="flex items-center gap-2">
                <Input
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  className="h-8 w-64"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") setEditingTitle(false)
                    if (e.key === "Escape") {
                      setTitleDraft(artifact?.title ?? "")
                      setEditingTitle(false)
                    }
                  }}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setEditingTitle(false)}
                >
                  <Check className="h-3 w-3" />
                </Button>
              </div>
            ) : (
              <button
                className="flex items-center gap-1.5 text-lg font-semibold text-foreground hover:text-foreground/80"
                onClick={() => setEditingTitle(true)}
              >
                {titleDraft || artifact?.title}
                <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            )}
          </div>
          <Button onClick={handleSave} disabled={updateArtifact.isPending}>
            {updateArtifact.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save
              </>
            )}
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6 space-y-4">
        {content?.categories.map((cat, catIdx) => {
          const isCollapsed = collapsedCategories.has(cat.category)
          const checkedCount = cat.items.filter((_, itemIdx) =>
            checkedItems.has(itemKey(catIdx, itemIdx)),
          ).length

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
                    const key = itemKey(catIdx, itemIdx)
                    const isChecked = checkedItems.has(key)
                    return (
                      <button
                        key={key}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-muted/50 transition-colors"
                        onClick={() => toggleItem(key)}
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

        {updateArtifact.isError && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            Failed to save. Please try again.
          </div>
        )}
      </div>
    </div>
  )
}
