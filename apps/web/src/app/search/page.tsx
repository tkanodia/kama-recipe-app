"use client"

import { useState, useMemo, useEffect } from "react"
import Image from "next/image"
import Link from "next/link"
import { useSearchParams, useRouter } from "next/navigation"
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
  Clock,
  Search,
  AlertCircle,
  RotateCcw,
  Loader2,
  Sparkles,
  X,
  SlidersHorizontal,
} from "lucide-react"
import { useTags } from "@/hooks/use-tags"
import { useSearch } from "@/hooks/use-search"
import { useIngredientSearch } from "@/hooks/use-ingredients"
import { useDebounce } from "@/hooks/use-debounce"
import { AskIntentBanner } from "@/components/search/ask-intent-banner"
import { SearchQualityBanner } from "@/components/search/search-quality-banner"
import type { SearchFilters } from "@kama/contracts"

export default function SearchPage() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") ?? "")
  const [selectedTags, setSelectedTags] = useState<string[]>(
    () => searchParams.get("tags")?.split(",").filter(Boolean) ?? []
  )
  const [maxCookTime, setMaxCookTime] = useState<string>(
    searchParams.get("maxCookTime") ?? ""
  )
  const [selectedIngredients, setSelectedIngredients] = useState<
    Array<{ id: string; name: string }>
  >([])
  const [ingredientQuery, setIngredientQuery] = useState("")
  const [showFilters, setShowFilters] = useState(
    !!(searchParams.get("tags") || searchParams.get("maxCookTime"))
  )

  const debouncedQuery = useDebounce(searchQuery, 400)

  const debouncedIngredientQuery = useDebounce(ingredientQuery, 300)
  const { data: ingredientSearchData } = useIngredientSearch(debouncedIngredientQuery, 8)
  const ingredientResults = ingredientSearchData?.items ?? []

  const filters: SearchFilters | undefined = useMemo(() => {
    const f: SearchFilters = {}
    if (selectedTags.length > 0) f.tagIds = selectedTags
    if (maxCookTime && !isNaN(Number(maxCookTime))) {
      f.maxCookTimeMinutes = Number(maxCookTime)
    }
    if (selectedIngredients.length > 0) {
      f.ingredientIds = selectedIngredients.map((i) => i.id)
    }
    return Object.keys(f).length > 0 ? f : undefined
  }, [selectedTags, maxCookTime, selectedIngredients])

  const hasInput = !!debouncedQuery || !!filters

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useSearch(debouncedQuery, filters, { enabled: hasInput })

  const { data: tagsData } = useTags("recipe")
  const tags = tagsData?.items ?? []

  const results = useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data],
  )

  const parsedQuery = data?.pages[0]?.parsedQuery
  const searchQualityReduced = data?.pages.some((p) => p.searchQualityReduced) ?? false

  useEffect(() => {
    const params = new URLSearchParams()
    if (debouncedQuery) params.set("q", debouncedQuery)
    if (selectedTags.length > 0) params.set("tags", selectedTags.join(","))
    if (maxCookTime) params.set("maxCookTime", maxCookTime)
    const qs = params.toString()
    router.replace(`/search${qs ? `?${qs}` : ""}`, { scroll: false })
  }, [debouncedQuery, selectedTags, maxCookTime, router])

  const toggleTagFilter = (tagId: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    )
  }

  const clearFilters = () => {
    setSearchQuery("")
    setSelectedTags([])
    setMaxCookTime("")
    setSelectedIngredients([])
    setIngredientQuery("")
  }

  const hasActiveFilters = selectedTags.length > 0 || !!maxCookTime || selectedIngredients.length > 0

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <Search className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Search</h1>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-4xl px-4 py-6">
        {/* Search Input */}
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search recipes... try &quot;quick chicken dinner&quot; or &quot;vegan desserts under 30 min&quot;"
                className="pl-9 pr-9"
                autoFocus
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <Button
              variant={showFilters ? "default" : "outline"}
              size="icon"
              onClick={() => setShowFilters(!showFilters)}
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </div>

          {/* Filter Bar */}
          {showFilters && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <div className="flex items-center gap-3">
                <label className="text-sm text-muted-foreground whitespace-nowrap">Max cook time</label>
                <Select value={maxCookTime || "any"} onValueChange={(v) => setMaxCookTime(v === "any" ? "" : v)}>
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="Any" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any</SelectItem>
                    <SelectItem value="15">15 min</SelectItem>
                    <SelectItem value="30">30 min</SelectItem>
                    <SelectItem value="45">45 min</SelectItem>
                    <SelectItem value="60">1 hour</SelectItem>
                    <SelectItem value="120">2 hours</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {tags.length > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Tags</p>
                  <div className="flex flex-wrap gap-1.5">
                    {tags.map((tag) => (
                      <Badge
                        key={tag.id}
                        variant={selectedTags.includes(tag.id) ? "default" : "outline"}
                        className="cursor-pointer font-normal"
                        onClick={() => toggleTagFilter(tag.id)}
                      >
                        {tag.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <p className="text-sm text-muted-foreground mb-2">Ingredients</p>
                {selectedIngredients.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {selectedIngredients.map((ing) => (
                      <Badge key={ing.id} variant="default" className="font-normal">
                        {ing.name}
                        <button
                          onClick={() => setSelectedIngredients((prev) => prev.filter((i) => i.id !== ing.id))}
                          className="ml-1 hover:text-destructive"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
                <div className="relative">
                  <Input
                    value={ingredientQuery}
                    onChange={(e) => setIngredientQuery(e.target.value)}
                    placeholder="Search ingredients to filter by..."
                    className="text-sm"
                  />
                  {ingredientQuery && ingredientResults.length > 0 && (
                    <div className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-md max-h-48 overflow-y-auto">
                      {ingredientResults
                        .filter((r) => !selectedIngredients.some((s) => s.id === r.id))
                        .map((result) => (
                          <button
                            key={result.id}
                            onClick={() => {
                              setSelectedIngredients((prev) => [...prev, { id: result.id, name: result.name }])
                              setIngredientQuery("")
                            }}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors"
                          >
                            {result.name}
                          </button>
                        ))}
                    </div>
                  )}
                </div>
              </div>

              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}
        </div>

        {/* Parsed Query Interpretation */}
        {parsedQuery && debouncedQuery && (
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-orange-500" />
            <span>
              Searching for &ldquo;{parsedQuery.semanticQuery}&rdquo;
              {parsedQuery.tagIds.length > 0 && ` with ${parsedQuery.tagIds.length} tag filter${parsedQuery.tagIds.length > 1 ? "s" : ""}`}
              {parsedQuery.ingredientIds.length > 0 && ` matching ${parsedQuery.ingredientIds.length} ingredient${parsedQuery.ingredientIds.length > 1 ? "s" : ""}`}
            </span>
          </div>
        )}

        {parsedQuery?.queryIntent === "ask" && debouncedQuery && (
          <AskIntentBanner query={debouncedQuery} />
        )}

        {searchQualityReduced && <SearchQualityBanner />}

        {/* Results */}
        <div className="mt-6">
          {!hasInput ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Search className="h-12 w-12 text-muted-foreground/30" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">Search your recipes</h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Looking for a recipe? Search here with natural language like &ldquo;easy weeknight dinners with chicken&rdquo;, or filter by tags and cook time.
              </p>
              <p className="mt-4 text-sm text-muted-foreground">
                Want to ask a question?{" "}
                <Link href="/ask" className="font-medium text-blue-400 underline hover:text-blue-300">
                  Try Ask
                </Link>
              </p>
            </div>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="mt-3 text-sm text-muted-foreground">Searching...</p>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">Search failed</h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Something went wrong. Please try again.
              </p>
              <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
                <RotateCcw className="h-4 w-4 mr-1" />
                Retry
              </Button>
            </div>
          ) : results.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Search className="h-12 w-12 text-muted-foreground/30" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">No results found</h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Try different keywords or adjust your filters.
              </p>
              {hasActiveFilters && (
                <Button variant="outline" className="mt-4" onClick={clearFilters}>
                  Clear filters
                </Button>
              )}
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground mb-4">
                {results.length} result{results.length !== 1 ? "s" : ""}
                {hasNextPage ? "+" : ""}
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {results.map((result) => (
                  <Card key={result.id} className="group overflow-hidden border border-border hover:border-foreground/20 transition-colors">
                    <Link href={`/recipes/${result.id}`}>
                      <div className="relative aspect-[16/10] w-full bg-muted overflow-hidden cursor-pointer">
                        {result.heroImageUrl ? (
                          <Image
                            src={result.heroImageUrl}
                            alt={result.title}
                            fill
                            className="object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center">
                            <span className="text-4xl font-bold text-muted-foreground/20">
                              {result.title.charAt(0)}
                            </span>
                          </div>
                        )}
                      </div>
                    </Link>
                    <CardContent className="p-4">
                      <Link href={`/recipes/${result.id}`}>
                        <h3 className="font-semibold text-foreground line-clamp-1 cursor-pointer hover:underline">
                          {result.title}
                        </h3>
                      </Link>
                      {result.description && (
                        <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                          {result.description}
                        </p>
                      )}

                      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                        {result.cookTimeMinutes && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {(result.prepTimeMinutes ?? 0) + result.cookTimeMinutes} min
                          </div>
                        )}
                        <div className="flex items-center gap-1 text-orange-500">
                          <Sparkles className="h-3 w-3" />
                          {Math.round(result.relevanceScore * 100)}% match
                        </div>
                      </div>

                      {result.matchReasons.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {result.matchReasons.slice(0, 3).map((reason, idx) => (
                            <Badge key={idx} variant="secondary" className="font-normal text-xs">
                              {reason}
                            </Badge>
                          ))}
                        </div>
                      )}

                      {result.recipeTags.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {result.recipeTags.slice(0, 3).map((tag) => (
                            <Badge key={tag.id} variant="outline" className="font-normal text-xs">
                              {tag.name}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>

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
            </>
          )}
        </div>
      </div>
    </div>
  )
}
