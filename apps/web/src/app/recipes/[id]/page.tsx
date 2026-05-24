"use client"

import { useState, useCallback, useMemo, useEffect } from "react"
import Image from "next/image"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Clock,
  Users,
  Minus,
  Plus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  SquarePen,
  MoreVertical,
  Calendar,
  Tag,
  Trash2,
  ExternalLink,
  FileText,
  ImageIcon,
  Share2,
  Copy,
  Heart,
  Printer,
  Archive,
  BookOpen,
  X,
  Loader2,
  AlertCircle,
  RotateCcw,
  MessageCircle,
  Send,
} from "lucide-react"
import { useRecipe, useDeleteRecipe } from "@/hooks/use-recipes"
import { useJournalEntries, useCreateJournalEntry, useDeleteJournalEntry } from "@/hooks/use-journal"
import { useTags } from "@/hooks/use-tags"
import { useApiClient } from "@/lib/api"
import { useCreateAskSession, useSendMessage } from "@/hooks/use-ask"
import type { AskMessage } from "@kama/contracts"
import { scaleIngredients, groupIngredients, type ScalableIngredient } from "@kama/shared"
import { RecipeDetailSkeleton, JournalEntrySkeleton } from "@/components/skeletons"
import { EmptyState } from "@/components/empty-state"
import { createPortal } from "react-dom"

export default function RecipeDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const recipeId = params.id as string
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [isDeleted, setIsDeleted] = useState(false)

  const { data: recipe, isLoading, isError, refetch } = useRecipe(recipeId, { enabled: !isDeleted })
  const { data: journalData } = useJournalEntries(recipeId, { enabled: !isDeleted })
  const { data: tagsData } = useTags("journal")
  const api = useApiClient()
  const createEntry = useCreateJournalEntry(recipeId)
  const deleteEntry = useDeleteJournalEntry(recipeId)
  const deleteRecipe = useDeleteRecipe()

  const [servingsOverride, setServingsOverride] = useState<number | null>(null)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isStoryOpen, setIsStoryOpen] = useState(false)
  
  const [newTagInput, setNewTagInput] = useState("")
  const [isAddingTag, setIsAddingTag] = useState(false)
  const [journalFiles, setJournalFiles] = useState<File[]>([])
  const [journalPreviews, setJournalPreviews] = useState<string[]>([])
  const [journalBody, setJournalBody] = useState("")
  const [isUploading, setIsUploading] = useState(false)
  const [carouselIndex, setCarouselIndex] = useState(0)

  const journalEntries = journalData?.items ?? []
  const tagOptions = tagsData?.items ?? []

  const r = recipe as Record<string, unknown> | undefined
  const baseServings = (r?.servings as number) || 4
  const servings = servingsOverride ?? baseServings
  const ingredientsRaw = (r?.ingredients ?? []) as Array<ScalableIngredient>

  const scaledIngredients = useMemo(
    () => scaleIngredients(ingredientsRaw, baseServings, servings),
    [ingredientsRaw, baseServings, servings],
  )

  const ingredientGroups = useMemo(
    () => groupIngredients(scaledIngredients),
    [scaledIngredients],
  )

  const toggleTag = useCallback((tagId: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId]
    )
  }, [])

  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      const fileArr = Array.from(files).slice(0, 2 - journalFiles.length)
      setJournalFiles((prev) => [...prev, ...fileArr].slice(0, 2))
      setJournalPreviews((prev) => [
        ...prev,
        ...fileArr.map((f) => URL.createObjectURL(f)),
      ].slice(0, 2))
    }
  }, [journalFiles.length])

  const removeJournalImage = useCallback((index: number) => {
    setJournalFiles((prev) => prev.filter((_, i) => i !== index))
    setJournalPreviews((prev) => {
      URL.revokeObjectURL(prev[index])
      return prev.filter((_, i) => i !== index)
    })
  }, [])

  const handleAddEntry = useCallback(async () => {
    if (!journalBody.trim()) return

    let mediaRefs: string[] = []
    if (journalFiles.length > 0) {
      setIsUploading(true)
      try {
        const uploads = await Promise.all(
          journalFiles.map(async (file) => {
            const { uploadUrl, assetRef } = await api.media.getPresignedUrl({
              fileName: file.name,
              contentType: file.type,
              context: "journal_media",
            })
            await fetch(uploadUrl, {
              method: "PUT",
              headers: { "Content-Type": file.type },
              body: file,
            })
            return assetRef
          })
        )
        mediaRefs = uploads
      } catch {
        setIsUploading(false)
        return
      }
      setIsUploading(false)
    }

    const tagObjs = selectedTags
      .map((id) => tagOptions.find((t) => t.id === id))
      .filter(Boolean)
      .map((t) => ({ id: t!.id, name: t!.name }))

    createEntry.mutate(
      { body: journalBody, tags: tagObjs, mediaRefs },
      {
        onSuccess: () => {
          setJournalBody("")
          setSelectedTags([])
          journalPreviews.forEach((url) => URL.revokeObjectURL(url))
          setJournalFiles([])
          setJournalPreviews([])
        },
      }
    )
  }, [journalBody, selectedTags, journalFiles, journalPreviews, createEntry, api.media])

  if (isLoading) {
    return <RecipeDetailSkeleton />
  }

  if (isError || !recipe) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-7 w-7 text-destructive" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load recipe</h3>
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">
          Something went wrong. Please try again.
        </p>
        <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
          <RotateCcw className="h-4 w-4 mr-1" />
          Retry
        </Button>
      </div>
    )
  }

  const title = (r?.title as string) ?? "Untitled"
  const description = r?.description as string | undefined
  const heroObj = r?.heroImage as { assetRef?: string } | undefined
  const heroImageUrl = heroObj?.assetRef as string | undefined
  const recipeTagsRaw = (r?.recipeTags ?? r?.tags ?? []) as Array<{ id?: string; name?: string } | string>
  const recipeTags = recipeTagsRaw.map((t) =>
    typeof t === "string" ? t : (t.name ?? "")
  )
  const prepTimeMinutes = r?.prepTimeMinutes as number | undefined
  const cookTimeMinutes = r?.cookTimeMinutes as number | undefined
  const stepsRaw = (r?.steps ?? []) as Array<{ order: number; text: string }>
  const galleryRaw = (r?.gallery ?? []) as Array<{ id: string; assetRef: string; thumbnailRef?: string; role: string }>
  const heroBase = heroImageUrl?.split("?")[0]
  const galleryImages = galleryRaw
    .filter((m) => m.role === "source_gallery")
    .filter((m, i, arr) => {
      const base = m.assetRef.split("?")[0]
      if (base === heroBase) return false
      return arr.findIndex((x) => x.assetRef.split("?")[0] === base) === i
    })
  const stepMediaMap = new Map(
    galleryRaw
      .filter((m) => m.role.startsWith("step_"))
      .map((m) => [parseInt(m.role.replace("step_", ""), 10), m.assetRef])
  )
  const provenance = r?.fieldProvenanceMap as Record<string, unknown> | undefined
  const provenanceSource = provenance?._source as { socialUrl?: string; discoveredUrl?: string; extractionMethod?: string } | undefined
  const sourceAssetId = r?.sourceAssetId as string | undefined
  const sourceUrl = r?.sourceUrl as string | undefined
  const sourceType = r?.sourceType as string | undefined
  const sourceImageUrl = r?.sourceImageUrl as string | undefined
  const nutrition = r?.nutrition as Record<string, string> | null | undefined
  const notes = (r?.notes ?? []) as Array<{ type: string; text: string }>
  const howToServe = r?.howToServe as string | null | undefined

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <div className="relative">
        <div className="relative h-[50vh] w-full bg-muted">
          {heroImageUrl ? (
            <Image
              src={heroImageUrl}
              alt={title}
              fill
              className="object-cover"
              priority
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <span className="text-6xl font-bold text-muted-foreground/20">{title.charAt(0)}</span>
            </div>
          )}
        </div>

        <div className="relative mx-auto max-w-2xl px-4 -mt-32">
          <Card className="border-0 shadow-lg">
            <CardContent className="p-6">
              <div className="flex items-start justify-between gap-4">
                <h1 className="text-3xl font-bold tracking-tight text-foreground">
                  {title}
                </h1>
                <div className="flex items-center gap-2 shrink-0">
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/recipes/${recipeId}/edit`}>
                      <SquarePen className="h-4 w-4" />
                      Edit
                    </Link>
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem><Share2 className="h-4 w-4 mr-2" />Share Recipe</DropdownMenuItem>
                      <DropdownMenuItem><Copy className="h-4 w-4 mr-2" />Duplicate</DropdownMenuItem>
                      <DropdownMenuItem><Printer className="h-4 w-4 mr-2" />Print</DropdownMenuItem>
                      <DropdownMenuItem><Heart className="h-4 w-4 mr-2" />Add to Favorites</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem><Archive className="h-4 w-4 mr-2" />Archive</DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onSelect={() => {
                          setTimeout(() => setShowDeleteDialog(true), 300)
                        }}
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete Recipe
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>

              {description && (
                <p className="mt-3 text-muted-foreground leading-relaxed">{description}</p>
              )}

              {recipeTags.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {recipeTags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="font-normal">{tag}</Badge>
                  ))}
                </div>
              )}

              <div className="mt-6 flex items-center gap-6 text-sm text-muted-foreground">
                {prepTimeMinutes != null && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <div><span className="text-foreground">Prep:</span> {prepTimeMinutes} min</div>
                  </div>
                )}
                {cookTimeMinutes != null && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <div><span className="text-foreground">Cook:</span> {cookTimeMinutes} min</div>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  <span className="text-foreground">Servings:</span>
                  <div className="flex items-center gap-1">
                    <Button variant="outline" size="icon" className="h-6 w-6" onClick={() => setServingsOverride(Math.max(1, servings - 1))}>
                      <Minus className="h-3 w-3" />
                    </Button>
                    <span className="w-6 text-center text-foreground">{servings}</span>
                    <Button variant="outline" size="icon" className="h-6 w-6" onClick={() => setServingsOverride(servings + 1)}>
                      <Plus className="h-3 w-3" />
                    </Button>
                    {[2, 3, 4].map((m) => (
                      <Button
                        key={m}
                        variant={servings === baseServings * m ? "default" : "outline"}
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => setServingsOverride(baseServings * m)}
                      >
                        {m}x
                      </Button>
                    ))}
                    {servingsOverride !== null && servingsOverride !== baseServings && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-muted-foreground"
                        onClick={() => setServingsOverride(null)}
                      >
                        <RotateCcw className="h-3 w-3 mr-1" />
                        {baseServings}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-2xl px-4 py-8">
        <Card className="border-0 shadow-sm">
          <CardContent className="p-6">
            <Tabs defaultValue="ingredients" className="w-full">
              <TabsList className="w-full">
                <TabsTrigger value="ingredients" className="flex-1">Ingredients</TabsTrigger>
                <TabsTrigger value="steps" className="flex-1">Steps</TabsTrigger>
              </TabsList>

              <TabsContent value="ingredients" className="mt-6">
                <div className="space-y-5">
                  {ingredientGroups.map((group) => (
                    <div key={group.label || "_default"}>
                      {group.label && (
                        <h4 className="text-sm font-semibold text-foreground/70 uppercase tracking-wide mb-2">
                          {group.label}
                        </h4>
                      )}
                      <ul className="space-y-2">
                        {group.items.map((ing, index) => (
                          <li key={index} className="flex items-start gap-3">
                            <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 shrink-0 mt-2" />
                            <span className="text-foreground leading-relaxed">{ing.text}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="steps" className="mt-6">
                {galleryImages.length > 0 && (
                  <div className="mb-6 pb-6 border-b border-border">
                    <div className="relative">
                      <div className="relative w-full rounded-lg overflow-hidden bg-muted">
                        <Image
                          src={galleryImages[carouselIndex]?.assetRef ?? ""}
                          alt={`Recipe photo ${carouselIndex + 1}`}
                          width={0}
                          height={0}
                          sizes="100vw"
                          className="w-full h-auto"
                        />
                      </div>

                      {galleryImages.length > 1 && (
                        <>
                          <Button
                            variant="secondary"
                            size="icon"
                            className="absolute left-2 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm shadow-md hover:bg-background"
                            onClick={() => setCarouselIndex((i) => (i - 1 + galleryImages.length) % galleryImages.length)}
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="secondary"
                            size="icon"
                            className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm shadow-md hover:bg-background"
                            onClick={() => setCarouselIndex((i) => (i + 1) % galleryImages.length)}
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>

                          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5">
                            {galleryImages.map((_, i) => (
                              <button
                                key={i}
                                className={`h-1.5 rounded-full transition-all ${i === carouselIndex ? "w-4 bg-white" : "w-1.5 bg-white/50"}`}
                                onClick={() => setCarouselIndex(i)}
                              />
                            ))}
                          </div>
                        </>
                      )}

                      <span className="absolute top-2 right-2 text-xs font-medium bg-background/70 backdrop-blur-sm text-foreground rounded-md px-2 py-0.5">
                        {carouselIndex + 1} / {galleryImages.length}
                      </span>
                    </div>
                  </div>
                )}

                <ol className="space-y-6">
                  {stepsRaw.map((step, index) => {
                    const stepImg = stepMediaMap.get(step.order ?? index + 1)
                    return (
                      <li key={index} className="flex gap-4">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium text-muted-foreground">
                          {index + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-foreground leading-relaxed">{step.text}</p>
                          {stepImg && (
                            <div className="mt-3 rounded-lg overflow-hidden bg-muted">
                              <Image src={stepImg} alt={`Step ${index + 1}`} width={0} height={0} sizes="100vw" className="w-full h-auto" />
                            </div>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ol>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Nutrition Facts */}
        {nutrition && Object.keys(nutrition).length > 0 && (
          <Card className="mt-6 border-0 shadow-sm">
            <CardContent className="p-6">
              <h2 className="text-xl font-semibold text-foreground mb-4">Nutrition Facts</h2>
              {nutrition.servingSize && (
                <p className="text-sm text-muted-foreground mb-3">
                  Per serving: {nutrition.servingSize}
                </p>
              )}
              <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                {nutrition.calories && (
                  <div className="col-span-2 flex justify-between border-b border-border pb-2 mb-1">
                    <span className="font-semibold text-foreground">Calories</span>
                    <span className="font-semibold text-foreground">{nutrition.calories}</span>
                  </div>
                )}
                {[
                  ["fat", "Total Fat"],
                  ["saturatedFat", "Saturated Fat"],
                  ["unsaturatedFat", "Unsaturated Fat"],
                  ["transFat", "Trans Fat"],
                  ["cholesterol", "Cholesterol"],
                  ["sodium", "Sodium"],
                  ["carbohydrates", "Total Carbs"],
                  ["fiber", "Dietary Fiber"],
                  ["sugar", "Sugars"],
                  ["protein", "Protein"],
                ].map(([key, label]) => {
                  const value = nutrition[key]
                  if (!value) return null
                  const isIndented = ["saturatedFat", "unsaturatedFat", "transFat", "fiber", "sugar"].includes(key)
                  return (
                    <div
                      key={key}
                      className={`flex justify-between py-1 border-b border-border/50 ${isIndented ? "pl-4" : ""}`}
                    >
                      <span className={`text-sm ${isIndented ? "text-muted-foreground" : "font-medium text-foreground"}`}>
                        {label}
                      </span>
                      <span className="text-sm text-foreground">{value}</span>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* How to Serve */}
        {howToServe && (
          <Card className="mt-6 border-0 shadow-sm">
            <CardContent className="p-6">
              <h2 className="text-xl font-semibold text-foreground mb-3">How to Serve</h2>
              <p className="text-sm text-foreground leading-relaxed">{howToServe}</p>
            </CardContent>
          </Card>
        )}

        {/* Chef Notes */}
        {notes.length > 0 && (
          <Card className="mt-6 border-0 shadow-sm">
            <CardContent className="p-6">
              <h2 className="text-xl font-semibold text-foreground mb-4">Chef&apos;s Notes</h2>
              <ul className="space-y-3">
                {notes.map((note, idx) => (
                  <li key={idx} className="flex items-start gap-3">
                    <Badge
                      variant="outline"
                      className="shrink-0 mt-0.5 text-xs capitalize"
                    >
                      {note.type}
                    </Badge>
                    <p className="text-sm text-foreground leading-relaxed">{note.text}</p>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Ask about this recipe */}
        <AskAboutRecipe recipeId={recipeId} />

        {/* Provenance */}
        {sourceAssetId && (
          <Card className="mt-6 border-0 shadow-sm">
            <Collapsible open={isStoryOpen} onOpenChange={setIsStoryOpen}>
              <CollapsibleTrigger asChild>
                <CardContent className="p-6 cursor-pointer hover:bg-muted/50 transition-colors">
                  <div className="flex items-center justify-center gap-2">
                    <h2 className="text-xl font-semibold text-foreground">How this recipe was created</h2>
                    <ChevronDown className={`h-5 w-5 text-muted-foreground transition-transform duration-200 ${isStoryOpen ? "rotate-180" : ""}`} />
                  </div>
                </CardContent>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <CardContent className="px-6 pb-6 pt-0">
                  <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50">
                    <FileText className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-foreground">Imported via ingestion pipeline</span>
                      {sourceUrl ? (
                        <a
                          href={sourceUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 block text-xs text-primary hover:underline truncate"
                        >
                          {sourceUrl}
                        </a>
                      ) : (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Source: {sourceType === "text" ? "Pasted text" : sourceType === "image" ? "Image upload" : sourceAssetId}
                        </p>
                      )}
                      {provenanceSource?.discoveredUrl && (
                        <div className="mt-2 pt-2 border-t border-border/50">
                          <p className="text-xs text-muted-foreground">Recipe extracted from</p>
                          <a
                            href={provenanceSource.discoveredUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-0.5 block text-xs text-primary hover:underline truncate"
                          >
                            {provenanceSource.discoveredUrl}
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                  {sourceImageUrl && (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-muted-foreground mb-2">Original image</p>
                      <div className="rounded-lg overflow-hidden border border-border bg-muted">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={sourceImageUrl}
                          alt="Original recipe source"
                          className="w-full h-auto"
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}

        {/* Cook Journal */}
        <Card className="mt-6 border-0 shadow-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-foreground">Cook Journal</h2>
              <span className="text-sm text-muted-foreground">
                {journalEntries.length} {journalEntries.length === 1 ? "entry" : "entries"}
              </span>
            </div>

            {/* New Entry Form */}
            <div className="mt-4 rounded-lg border border-border p-4">
              <Textarea
                value={journalBody}
                onChange={(e) => setJournalBody(e.target.value)}
                placeholder="How did it turn out? Any tweaks or notes..."
                className="min-h-24 border-0 bg-muted/50 resize-none focus-visible:ring-0"
              />

              {journalPreviews.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {journalPreviews.map((img, index) => (
                    <div key={index} className="relative group">
                      <div className="relative h-16 w-16 rounded-md overflow-hidden">
                        <Image src={img} alt={`Upload ${index + 1}`} fill className="object-cover" />
                      </div>
                      <button
                        onClick={() => removeJournalImage(index)}
                        className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-3 flex items-start gap-3">
                <Tag className="h-4 w-4 text-muted-foreground mt-1.5" />
                <div className="flex flex-wrap gap-2 flex-1">
                  {tagOptions.map((tag) => (
                    <Badge
                      key={tag.id}
                      variant={selectedTags.includes(tag.id) ? "default" : "outline"}
                      className="cursor-pointer font-normal"
                      onClick={() => toggleTag(tag.id)}
                    >
                      {tag.name}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex items-center gap-2">
                <Button
                  onClick={() => void handleAddEntry()}
                  disabled={!journalBody.trim() || createEntry.isPending || isUploading}
                  className="bg-muted-foreground hover:bg-muted-foreground/90 text-background"
                >
                  {isUploading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Uploading...</>
                  ) : createEntry.isPending ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Adding...</>
                  ) : "Add Entry"}
                </Button>
                <label>
                  <input type="file" accept="image/*" multiple className="hidden" onChange={handleImageUpload} />
                  <Button variant="outline" size="icon" asChild>
                    <span className="cursor-pointer"><ImageIcon className="h-4 w-4" /></span>
                  </Button>
                </label>
              </div>
            </div>

            {/* Journal Entries */}
            <div className="mt-4 space-y-4">
              {journalEntries.length === 0 && (
                <div className="flex flex-col items-center py-8 text-center">
                  <BookOpen className="h-8 w-8 text-muted-foreground/40" />
                  <p className="mt-3 text-sm text-muted-foreground">
                    No journal entries yet. Record your cooking notes above.
                  </p>
                </div>
              )}
              {journalEntries.map((entry) => (
                <div key={entry.id} className="rounded-lg border border-border p-4">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-foreground leading-relaxed">{entry.body}</p>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => deleteEntry.mutate(entry.id)}
                      disabled={deleteEntry.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  {entry.media && entry.media.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {entry.media.map((m) => (
                        <div key={m.id} className="relative h-20 w-20 rounded-md overflow-hidden">
                          <Image src={m.url} alt="Entry image" fill className="object-cover" />
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    {entry.cookedOn && <span>Cooked on {entry.cookedOn}</span>}
                    {entry.tags.map((tag) => (
                      <Badge key={tag.id} variant="secondary" className="font-normal">{tag.name}</Badge>
                    ))}
                  </div>
                  <div className="mt-2 text-right text-sm text-muted-foreground">
                    {new Date(entry.createdAt).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {showDeleteDialog && <DeleteRecipePortal
        isPending={deleteRecipe.isPending}
        onConfirm={() => {
          setIsDeleted(true)
          deleteRecipe.mutate(recipeId, {
            onSuccess: () => {
              setShowDeleteDialog(false)
              router.push("/recipes")
            },
            onError: () => {
              setIsDeleted(false)
            },
          })
        }}
        onCancel={() => { if (!deleteRecipe.isPending) setShowDeleteDialog(false) }}
      />}
    </div>
  )
}

function DeleteRecipePortal({
  isPending,
  onConfirm,
  onCancel,
}: {
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
          This will permanently delete this recipe, all journal entries, and media. This cannot be undone.
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

const RECIPE_QUESTIONS = [
  "What can I substitute for...?",
  "How do I know when it's done?",
  "Tips for making this ahead of time?",
]

function AskAboutRecipe({ recipeId }: { recipeId: string }) {
  const [question, setQuestion] = useState("")
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<AskMessage[]>([])
  const createSession = useCreateAskSession()
  const sendMessage = useSendMessage(sessionId ?? "")

  const handleAsk = (q: string) => {
    const trimmed = q.trim()
    if (!trimmed) return

    if (!sessionId) {
      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          role: "user",
          content: trimmed,
          createdAt: new Date().toISOString(),
        },
      ])
      createSession.mutate(
        { question: trimmed, recipeId },
        {
          onSuccess: (data) => {
            setSessionId(data.sessionId)
            setMessages((prev) => [
              ...prev.filter((m) => m.role === "user"),
              data.message,
            ])
          },
        },
      )
    } else {
      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          role: "user",
          content: trimmed,
          createdAt: new Date().toISOString(),
        },
      ])
      sendMessage.mutate(
        { question: trimmed },
        {
          onSuccess: (data) => {
            setMessages((prev) => [...prev, data.message])
          },
        },
      )
    }
    setQuestion("")
  }

  const isPending = createSession.isPending || sendMessage.isPending

  return (
    <Card className="mt-6 border-0 shadow-sm">
      <CardContent className="p-6">
        <div className="flex items-center gap-2 mb-2">
          <MessageCircle className="h-5 w-5 text-orange-500" />
          <h2 className="text-xl font-semibold text-foreground">
            Ask about this recipe
          </h2>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Get expert cooking tips, substitutions, and technique advice
        </p>

        <div className="flex flex-wrap gap-1.5 mb-4">
          {RECIPE_QUESTIONS.map((q) => (
            <Badge
              key={q}
              variant="outline"
              className="cursor-pointer font-normal hover:bg-secondary/80"
              onClick={() => handleAsk(q)}
            >
              {q}
            </Badge>
          ))}
        </div>

        {messages.length > 0 && (
          <div className="mb-4 space-y-3 max-h-80 overflow-y-auto rounded-lg border border-border p-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`text-sm ${
                  msg.role === "user"
                    ? "text-right text-muted-foreground"
                    : "text-foreground"
                }`}
              >
                <span
                  className={`inline-block max-w-[90%] rounded-lg px-3 py-2 ${
                    msg.role === "user"
                      ? "bg-foreground/5"
                      : "bg-muted"
                  }`}
                >
                  {msg.content}
                </span>
              </div>
            ))}
            {isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Thinking...
              </div>
            )}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleAsk(question)
          }}
          className="flex items-center gap-2"
        >
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about this recipe..."
            disabled={isPending}
          />
          <Button
            type="submit"
            size="icon"
            disabled={!question.trim() || isPending}
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>

        {(createSession.isError || sendMessage.isError) && (
          <p className="mt-2 text-sm text-destructive">
            Something went wrong. Please try again.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
