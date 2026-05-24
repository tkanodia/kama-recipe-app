"use client"

import { useState, useMemo, useEffect, useCallback } from "react"
import Image from "next/image"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Clock,
  Plus,
  Search,
  BookOpen,
  FileEdit,
  UtensilsCrossed,
  AlertCircle,
  RotateCcw,
  MoreVertical,
  SquarePen,
  Trash2,
  Share2,
  Copy,
  Heart,
  Archive,
  Loader2,
} from "lucide-react"
import { useRecipes, useDeleteRecipe } from "@/hooks/use-recipes"
import { useTags } from "@/hooks/use-tags"
import { usePantryItems, useFeasibility } from "@/hooks/use-pantry"
import { RecipeLibrarySkeleton } from "@/components/skeletons"
import { EmptyState } from "@/components/empty-state"
import { createPortal } from "react-dom"
import { useDebounce } from "@/hooks/use-debounce"
import { AskIntentBanner } from "@/components/search/ask-intent-banner"
import { SearchQualityBanner } from "@/components/search/search-quality-banner"
import type { FeasibilityRecipe } from "@kama/contracts"

type StatusFilter = "all" | "canonical" | "drafts"
type SortOption = "updated_desc" | "created_desc" | "title_asc"
type PantryFilter = "all" | "ready" | "almost"

function DeleteConfirmPortal({
  title,
  isPending,
  onConfirm,
  onCancel,
}: {
  title: string
  isPending: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    document.body.style.pointerEvents = ""
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isPending) onCancel()
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [isPending, onCancel])

  if (!mounted) return null

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" style={{ pointerEvents: "auto" }}>
      <div
        className="fixed inset-0 bg-black/80"
        onClick={() => { if (!isPending) onCancel() }}
        style={{ pointerEvents: "auto" }}
      />
      <div
        className="relative w-full max-w-lg mx-4 rounded-lg border bg-background p-6 shadow-lg"
        style={{ pointerEvents: "auto", zIndex: 10000 }}
      >
        <h2 className="text-lg font-semibold">Delete recipe?</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          &ldquo;{title}&rdquo; will be permanently deleted along with all journal entries and media. This cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            disabled={isPending}
            onClick={onCancel}
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={onConfirm}
            className="inline-flex items-center justify-center rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
          >
            {isPending ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Deleting...</>
            ) : (
              "Delete"
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

export default function RecipeLibraryPage() {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [sortBy, setSortBy] = useState<SortOption>("updated_desc")
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)
  const [pantryMode, setPantryMode] = useState(false)
  const [pantryFilter, setPantryFilter] = useState<PantryFilter>("all")

  const debouncedSearch = useDebounce(searchQuery, 300)

  const PAGE_SIZE = 12

  const apiParams = useMemo(() => {
    const p: Record<string, string | number | undefined> = {
      sort: sortBy,
      limit: PAGE_SIZE,
    }
    if (statusFilter !== "all") {
      p.status = statusFilter === "drafts" ? "draft" : statusFilter
    }
    if (debouncedSearch) {
      p.search = debouncedSearch
    }
    if (selectedTags.length > 0) {
      p.tags = selectedTags.join(",")
    }
    if (pantryMode) {
      p.pantry = "true"
    }
    return p
  }, [sortBy, statusFilter, debouncedSearch, selectedTags, pantryMode])

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useRecipes(apiParams)

  const { data: tagsData } = useTags("recipe")
  const deleteRecipe = useDeleteRecipe()

  const { data: pantryData } = usePantryItems()
  const hasPantryItems = (pantryData?.items?.length ?? 0) > 0
  const { data: feasibilityData } = useFeasibility({
    enabled: pantryMode && hasPantryItems,
  })

  const feasibilityMap = useMemo(() => {
    if (!feasibilityData) return new Map<string, { tier: "ready" | "almost" | "not"; recipe: FeasibilityRecipe }>()
    const m = new Map<string, { tier: "ready" | "almost" | "not"; recipe: FeasibilityRecipe }>()
    for (const r of feasibilityData.fullyFeasible) m.set(r.recipeId, { tier: "ready", recipe: r })
    for (const r of feasibilityData.partiallyFeasible) m.set(r.recipeId, { tier: "almost", recipe: r })
    for (const r of feasibilityData.notFeasible) m.set(r.recipeId, { tier: "not", recipe: r })
    return m
  }, [feasibilityData])

  const recipes = useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data],
  )
  const parsedQuery = data?.pages[0]?.parsedQuery
  const searchQualityReduced =
    debouncedSearch.length > 0 &&
    (data?.pages.some((page) => page.searchQualityReduced) ?? false)
  const tags = tagsData?.items ?? []

  const filteredRecipes = useMemo(() => {
    if (!pantryMode || pantryFilter === "all") return recipes
    return recipes.filter((r) => {
      if (r.feasibilityStatus) {
        if (pantryFilter === "ready") return r.feasibilityStatus === "fully_feasible"
        if (pantryFilter === "almost") return r.feasibilityStatus === "partially_feasible"
        return false
      }
      const entry = feasibilityMap.get(r.id)
      if (!entry) return false
      return entry.tier === pantryFilter
    })
  }, [recipes, pantryMode, pantryFilter, feasibilityMap])

  const toggleTagFilter = (tagId: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    )
  }

  const clearFilters = () => {
    setSearchQuery("")
    setStatusFilter("all")
    setSelectedTags([])
    setPantryFilter("all")
  }

  const hasActiveFilters = searchQuery || statusFilter !== "all" || selectedTags.length > 0 || pantryFilter !== "all"

  const handleConfirmDelete = useCallback(() => {
    if (!deleteTarget) return
    deleteRecipe.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    })
  }, [deleteTarget, deleteRecipe])

  const handleCancelDelete = useCallback(() => {
    if (!deleteRecipe.isPending) setDeleteTarget(null)
  }, [deleteRecipe.isPending])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <UtensilsCrossed className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">Recipes</h1>
            </div>
          </div>
        </div>
        <div className="mx-auto max-w-4xl px-4 py-6">
          <RecipeLibrarySkeleton />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b border-border bg-background">
          <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <UtensilsCrossed className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">Recipes</h1>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-7 w-7 text-destructive" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load recipes</h3>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            Something went wrong. Please try again.
          </p>
          <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
            <RotateCcw className="h-4 w-4 mr-1" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <UtensilsCrossed className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Recipes</h1>
            <Badge variant="secondary" className="font-normal">
              {recipes.length}{hasNextPage ? "+" : ""}
            </Badge>
          </div>
          <Button asChild>
            <Link href="/ingest">
              <Plus className="h-4 w-4 mr-1" />
              Add Recipe
            </Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-4xl px-4 py-6">
        {/* Filter Bar */}
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search recipes..."
                className="pl-9"
              />
            </div>
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="updated_desc">Recently updated</SelectItem>
                <SelectItem value="created_desc">Recently added</SelectItem>
                <SelectItem value="title_asc">Title A–Z</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex rounded-lg border border-border p-0.5">
              {(["all", "canonical", "drafts"] as StatusFilter[]).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`rounded-md px-3 py-1 text-sm transition-colors ${
                    statusFilter === status
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {status === "all" ? "All" : status === "canonical" ? "Saved" : "Drafts"}
                </button>
              ))}
            </div>

            <div className="h-5 w-px bg-border" />

            {tags.slice(0, 6).map((tag) => (
              <Badge
                key={tag.id}
                variant={selectedTags.includes(tag.id) ? "default" : "outline"}
                className="cursor-pointer font-normal"
                onClick={() => toggleTagFilter(tag.id)}
              >
                {tag.name}
              </Badge>
            ))}

            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Clear all
              </button>
            )}
          </div>

          {hasPantryItems && (
            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={() => {
                  setPantryMode(!pantryMode)
                  setPantryFilter("all")
                }}
                className={`flex items-center gap-1.5 rounded-md border px-3 py-1 text-sm transition-colors ${
                  pantryMode
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                <UtensilsCrossed className="h-3.5 w-3.5" />
                Pantry
              </button>

              {pantryMode && (
                <>
                  <div className="h-5 w-px bg-border" />
                  <div className="flex rounded-lg border border-border p-0.5">
                    {(["all", "ready", "almost"] as PantryFilter[]).map((f) => (
                      <button
                        key={f}
                        onClick={() => setPantryFilter(f)}
                        className={`rounded-md px-3 py-1 text-sm transition-colors ${
                          pantryFilter === f
                            ? "bg-foreground text-background"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {f === "all" ? "All" : f === "ready" ? "Can make now" : "Almost there"}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {parsedQuery?.queryIntent === "ask" && debouncedSearch && (
          <AskIntentBanner query={debouncedSearch} />
        )}

        {searchQualityReduced && <SearchQualityBanner />}

        {/* Results */}
        <div className="mt-6">
          {filteredRecipes.length === 0 ? (
            hasActiveFilters ? (
              <EmptyState
                icon={Search}
                title="No recipes match"
                description="Try adjusting your filters or search query."
                action={{ label: "Clear filters", variant: "outline", onClick: clearFilters }}
              />
            ) : (
              <EmptyState
                icon={BookOpen}
                title="No recipes yet"
                description="Add your first recipe from a URL, image, or text."
                action={{ label: "Add your first recipe", href: "/ingest", icon: Plus }}
              />
            )
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {filteredRecipes.map((recipe) => {
                const href = recipe.kind === "draft" ? `/drafts/${recipe.id}` : `/recipes/${recipe.id}`
                const feasibility = pantryMode
                  ? recipe.feasibilityStatus
                    ? { tier: recipe.feasibilityStatus === "fully_feasible" ? "ready" as const : recipe.feasibilityStatus === "partially_feasible" ? "almost" as const : "not" as const }
                    : feasibilityMap.get(recipe.id)
                  : undefined
                return (
                  <Card key={recipe.id} className="group overflow-hidden border border-border hover:border-foreground/20 transition-colors">
                    <Link href={href}>
                      <div className="relative aspect-[16/10] w-full bg-muted overflow-hidden cursor-pointer">
                        {recipe.heroImageUrl ? (
                          <Image
                            src={recipe.heroImageUrl}
                            alt={recipe.title}
                            fill
                            className="object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center">
                            <span className="text-4xl font-bold text-muted-foreground/20">
                              {recipe.title.charAt(0)}
                            </span>
                          </div>
                        )}
                        {recipe.kind === "draft" && (
                          <Badge className="absolute top-2 left-2 bg-background/80 text-foreground backdrop-blur border-0">
                            <FileEdit className="h-3 w-3 mr-1" />
                            Draft
                          </Badge>
                        )}
                        {feasibility?.tier === "ready" && (
                          <Badge className="absolute top-2 right-2 bg-green-500 text-white border-0">
                            Ready
                          </Badge>
                        )}
                        {feasibility?.tier === "almost" && (
                          <Badge className="absolute top-2 right-2 bg-orange-500 text-white border-0">
                            Almost
                          </Badge>
                        )}
                      </div>
                    </Link>

                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <Link href={href} className="flex-1 min-w-0">
                          <h3 className="font-semibold text-foreground line-clamp-1 cursor-pointer hover:underline">
                            {recipe.title}
                          </h3>
                        </Link>
                        {recipe.kind === "canonical" && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 -mt-0.5" onClick={(e) => e.stopPropagation()}>
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-44">
                              <DropdownMenuItem onSelect={() => router.push(`/recipes/${recipe.id}/edit`)}>
                                <SquarePen className="h-4 w-4 mr-2" />Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem><Share2 className="h-4 w-4 mr-2" />Share</DropdownMenuItem>
                              <DropdownMenuItem><Copy className="h-4 w-4 mr-2" />Duplicate</DropdownMenuItem>
                              <DropdownMenuItem><Heart className="h-4 w-4 mr-2" />Favorite</DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem><Archive className="h-4 w-4 mr-2" />Archive</DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onSelect={() => {
                                  const target = { id: recipe.id, title: recipe.title }
                                  setTimeout(() => setDeleteTarget(target), 300)
                                }}
                              >
                                <Trash2 className="h-4 w-4 mr-2" />Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                      {recipe.description && (
                        <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                          {recipe.description}
                        </p>
                      )}

                      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                        {recipe.cookTimeMinutes && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {(recipe.prepTimeMinutes ?? 0) + recipe.cookTimeMinutes} min
                          </div>
                        )}
                        {(recipe.journalEntryCount ?? 0) > 0 && (
                          <div className="flex items-center gap-1">
                            <BookOpen className="h-3 w-3" />
                            {recipe.journalEntryCount} {recipe.journalEntryCount === 1 ? "entry" : "entries"}
                          </div>
                        )}
                      </div>

                      {recipe.recipeTags.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {recipe.recipeTags.slice(0, 3).map((tag) => (
                            <Badge
                              key={tag.id}
                              variant="secondary"
                              className="font-normal text-xs"
                            >
                              {tag.name}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}

          {hasNextPage && (
            <div className="mt-8 text-center">
              <Button
                variant="outline"
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Loading...</>
                ) : (
                  "Load more"
                )}
              </Button>
            </div>
          )}
        </div>
      </div>

      {deleteTarget && (
        <DeleteConfirmPortal
          title={deleteTarget.title}
          isPending={deleteRecipe.isPending}
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
        />
      )}
    </div>
  )
}
