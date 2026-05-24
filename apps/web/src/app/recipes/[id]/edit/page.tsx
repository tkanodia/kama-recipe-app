"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import { useRouter, useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Plus,
  Trash2,
  ChevronUp,
  ChevronDown,
  X,
  AlertCircle,
  Loader2,
  RotateCcw,
  Clock,
  Users,
  Upload,
  ImageIcon,
} from "lucide-react"
import { useRecipe, useUpdateRecipe } from "@/hooks/use-recipes"
import { useTags, useCreateTag } from "@/hooks/use-tags"
import { usePresignedUrl } from "@/hooks/use-media"
import { useApiClient } from "@/lib/api"
import { DraftDetailSkeleton } from "@/components/skeletons"
import type { RecipeIngredientRow, RecipeStepRow } from "@kama/contracts"

type TagObj = { id: string; name: string }

const unitOptions = [
  "whole", "oz", "lb", "g", "kg", "cup", "cups", "tbsp", "tsp",
  "ml", "l", "large", "medium", "small", "cloves", "slices",
  "pieces", "bottle", "can", "bunch", "pinch",
]

type LocalIngredient = {
  id: string
  text: string
  quantity: string
  unit: string
  section: string
}

type LocalStep = {
  id: string
  text: string
}

export default function RecipeEditPage() {
  const router = useRouter()
  const params = useParams()
  const recipeId = params.id as string

  const { data: recipe, isLoading, isError, refetch } = useRecipe(recipeId)
  const updateMutation = useUpdateRecipe(recipeId)
  const { data: tagsData } = useTags("recipe")
  const createTagMutation = useCreateTag()
  const presignedUrl = usePresignedUrl()
  const api = useApiClient()
  const availableTags: TagObj[] = useMemo(() => tagsData?.items?.map((t) => ({ id: t.id, name: t.name })) ?? [], [tagsData])

  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [prepTime, setPrepTime] = useState(0)
  const [cookTime, setCookTime] = useState(0)
  const [servings, setServings] = useState(0)
  const [heroImage, setHeroImage] = useState<string | null>(null)
  const [heroMediaId, setHeroMediaId] = useState<string | null>(null)
  const [isUploadingHero, setIsUploadingHero] = useState(false)
  const [pendingHeroDelete, setPendingHeroDelete] = useState<{ mediaId: string; imageUrl: string } | null>(null)
  const [tags, setTags] = useState<TagObj[]>([])
  const [ingredients, setIngredients] = useState<LocalIngredient[]>([])
  const [steps, setSteps] = useState<LocalStep[]>([])

  const [initialized, setInitialized] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false)
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [newTagInput, setNewTagInput] = useState("")
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false)

  useEffect(() => {
    if (recipe && !initialized) {
      const r = recipe as Record<string, unknown>
      setTitle((r.title as string) ?? "")
      setDescription((r.description as string) ?? "")
      setPrepTime((r.prepTimeMinutes as number) ?? 0)
      setCookTime((r.cookTimeMinutes as number) ?? 0)
      setServings((r.servings as number) ?? 0)

      const heroObj = r.heroImage as { id?: string; assetRef?: string } | undefined | null
      setHeroImage(heroObj?.assetRef ?? null)
      setHeroMediaId(heroObj?.id ?? null)

      const rawTags = (r.recipeTags ?? []) as Array<{ id?: string; name?: string } | string>
      setTags(rawTags.map((t) => {
        if (typeof t === "string") return { id: t, name: t }
        return { id: t.id ?? t.name ?? "", name: t.name ?? "" }
      }))

      const rawIngs = (r.ingredients ?? []) as Array<Record<string, unknown>>
      setIngredients(rawIngs.map((ing, i) => ({
        id: String(i),
        text: (ing.text as string) ?? "",
        quantity: (ing.quantity as string) ?? "",
        unit: (ing.unit as string) ?? "",
        section: (ing.section as string) ?? "",
      })))

      const rawSteps = (r.steps ?? []) as Array<Record<string, unknown>>
      setSteps(rawSteps.map((s, i) => ({
        id: String(i),
        text: (s.text as string) ?? "",
      })))

      setInitialized(true)
    }
  }, [recipe, initialized])

  useEffect(() => {
    if (!initialized) return
    setIsDirty(true)
  }, [title, description, prepTime, cookTime, servings, heroImage, tags, ingredients, steps, initialized])

  const handleNavigation = useCallback((path: string) => {
    if (isDirty) {
      setPendingNavigation(path)
      setShowUnsavedDialog(true)
    } else {
      router.push(path)
    }
  }, [isDirty, router])

  const confirmNavigation = () => {
    setPendingHeroDelete(null)
    if (pendingNavigation) router.push(pendingNavigation)
    setShowUnsavedDialog(false)
    setPendingNavigation(null)
  }

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}
    if (!title.trim()) newErrors.title = "Title is required"
    ingredients.forEach((ing, index) => {
      if (!ing.text.trim()) newErrors[`ingredient-${index}`] = "Ingredient text is required"
    })
    steps.forEach((step, index) => {
      if (!step.text.trim()) newErrors[`step-${index}`] = "Step instruction is required"
    })
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = async () => {
    if (!validate()) return

    const body = {
      title,
      description: description || null,
      prepTimeMinutes: prepTime || null,
      cookTimeMinutes: cookTime || null,
      servings: servings || null,
      ingredients: ingredients.map((ing): RecipeIngredientRow => ({
        text: ing.text,
        quantity: ing.quantity || null,
        unit: ing.unit || null,
        section: ing.section || null,
      })),
      steps: steps.map((s, i): RecipeStepRow => ({
        order: i + 1,
        text: s.text,
      })),
      recipeTags: tags.map((t) => t.id),
    }

    updateMutation.mutate(body, {
      onSuccess: async () => {
        if (pendingHeroDelete) {
          try {
            await api.media.deleteMedia(recipeId, pendingHeroDelete.mediaId)
          } catch { /* best-effort cleanup */ }
          setPendingHeroDelete(null)
        }
        setIsDirty(false)
        router.push(`/recipes/${recipeId}`)
      },
    })
  }

  const addIngredient = () => {
    setIngredients([...ingredients, {
      id: Date.now().toString(),
      text: "", quantity: "", unit: "", section: "",
    }])
  }

  const updateIngredient = (index: number, updates: Partial<LocalIngredient>) => {
    const updated = [...ingredients]
    updated[index] = { ...updated[index], ...updates }
    setIngredients(updated)
  }

  const removeIngredient = (index: number) => setIngredients(ingredients.filter((_, i) => i !== index))

  const moveIngredient = (index: number, direction: "up" | "down") => {
    if ((direction === "up" && index === 0) || (direction === "down" && index === ingredients.length - 1)) return
    const newIndex = direction === "up" ? index - 1 : index + 1
    const updated = [...ingredients]
    const [removed] = updated.splice(index, 1)
    updated.splice(newIndex, 0, removed)
    setIngredients(updated)
  }

  const addStep = () => {
    setSteps([...steps, { id: Date.now().toString(), text: "" }])
  }

  const updateStep = (index: number, updates: Partial<LocalStep>) => {
    const updated = [...steps]
    updated[index] = { ...updated[index], ...updates }
    setSteps(updated)
  }

  const removeStep = (index: number) => setSteps(steps.filter((_, i) => i !== index))

  const moveStep = (index: number, direction: "up" | "down") => {
    if ((direction === "up" && index === 0) || (direction === "down" && index === steps.length - 1)) return
    const newIndex = direction === "up" ? index - 1 : index + 1
    const updated = [...steps]
    const [removed] = updated.splice(index, 1)
    updated.splice(newIndex, 0, removed)
    setSteps(updated)
  }

  const toggleTag = (tag: TagObj) => {
    setTags((prev) =>
      prev.some((t) => t.id === tag.id)
        ? prev.filter((t) => t.id !== tag.id)
        : [...prev, tag]
    )
  }

  const addCustomTag = () => {
    const trimmed = newTagInput.trim().toLowerCase()
    if (!trimmed || tags.some((t) => t.name === trimmed)) return
    createTagMutation.mutate(
      { domain: "recipe", name: trimmed },
      {
        onSuccess: (result) => {
          setTags((prev) => [...prev, { id: result.id, name: result.name }])
          setNewTagInput("")
        },
      },
    )
  }

  const removeTag = (tagId: string) => setTags(tags.filter((t) => t.id !== tagId))

  const handleHeroUpload = async (file: File) => {
    setIsUploadingHero(true)
    try {
      const presigned = await presignedUrl.mutateAsync({
        fileName: file.name,
        contentType: file.type,
        context: "recipe_media",
      })
      await fetch(presigned.uploadUrl, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      })
      const result = await api.media.registerMedia(recipeId, {
        assetRef: presigned.assetRef,
        role: "hero",
      })
      const mediaResult = result as { id?: string; assetRef?: string }
      setHeroMediaId(mediaResult.id ?? null)
      setHeroImage(mediaResult.assetRef ?? presigned.assetRef)
      refetch()
    } catch {
      setErrors((prev) => ({ ...prev, hero: "Failed to upload image" }))
    } finally {
      setIsUploadingHero(false)
    }
  }

  const handleHeroRemove = () => {
    if (!heroMediaId || !heroImage) return
    setPendingHeroDelete({ mediaId: heroMediaId, imageUrl: heroImage })
    setHeroImage(null)
    setHeroMediaId(null)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4">
            <h1 className="text-lg font-semibold text-foreground">Edit Recipe</h1>
          </div>
        </div>
        <DraftDetailSkeleton />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-7 w-7 text-destructive" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load recipe</h3>
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">Something went wrong.</p>
        <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
          <RotateCcw className="h-4 w-4 mr-1" /> Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Sticky Header */}
      <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-foreground">Edit Recipe</h1>
            {isDirty && <Badge variant="secondary" className="text-xs">Unsaved</Badge>}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => handleNavigation(`/recipes/${recipeId}`)}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={!isDirty || updateMutation.isPending}>
              {updateMutation.isPending ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Saving</> : "Save Changes"}
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-6">
        {/* Hero Image */}
        <div className="relative mb-6 aspect-[21/9] w-full overflow-hidden rounded-xl bg-muted group">
          {heroImage ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={heroImage} alt="Recipe hero" className="h-full w-full object-cover" />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100">
                <label className="cursor-pointer rounded-full bg-white/90 p-2.5 hover:bg-white transition-colors shadow-sm">
                  <Upload className="h-4 w-4 text-foreground" />
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) handleHeroUpload(f)
                    }}
                  />
                </label>
                <button
                  onClick={handleHeroRemove}
                  className="rounded-full bg-white/90 p-2.5 hover:bg-white transition-colors shadow-sm"
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </button>
              </div>
            </>
          ) : (
            <label className="flex h-full w-full cursor-pointer flex-col items-center justify-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
              {isUploadingHero ? (
                <Loader2 className="h-8 w-8 animate-spin" />
              ) : (
                <>
                  <ImageIcon className="h-8 w-8" />
                  <span className="text-sm font-medium">Add a photo</span>
                </>
              )}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                disabled={isUploadingHero}
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) handleHeroUpload(f)
                }}
              />
            </label>
          )}
          {isUploadingHero && heroImage && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <Loader2 className="h-8 w-8 animate-spin text-white" />
            </div>
          )}
        </div>
        {errors.hero && (
          <p className="mb-4 -mt-4 text-sm text-destructive flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />{errors.hero}
          </p>
        )}

        {/* Title & Description */}
        <div className="space-y-4">
          <div>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Recipe title"
              className={`text-2xl font-semibold border-0 border-b rounded-none px-0 h-auto py-2 focus-visible:ring-0 focus-visible:border-foreground ${errors.title ? "border-destructive" : "border-border"}`}
            />
            {errors.title && (
              <p className="mt-1.5 text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />{errors.title}
              </p>
            )}
          </div>

          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="A brief description of the recipe..."
            className="min-h-16 resize-none border-0 bg-transparent px-0 text-muted-foreground focus-visible:ring-0"
          />
        </div>

        {/* Metadata row */}
        <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 py-4 border-y border-border">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <Label className="text-sm text-muted-foreground whitespace-nowrap">Prep</Label>
            <Input
              type="number"
              value={prepTime || ""}
              onChange={(e) => setPrepTime(Number(e.target.value) || 0)}
              placeholder="—"
              className="w-16 h-8 text-center text-sm border-border/50"
            />
            <span className="text-xs text-muted-foreground">min</span>
          </div>

          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <Label className="text-sm text-muted-foreground whitespace-nowrap">Cook</Label>
            <Input
              type="number"
              value={cookTime || ""}
              onChange={(e) => setCookTime(Number(e.target.value) || 0)}
              placeholder="—"
              className="w-16 h-8 text-center text-sm border-border/50"
            />
            <span className="text-xs text-muted-foreground">min</span>
          </div>

          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-muted-foreground" />
            <Label className="text-sm text-muted-foreground">Serves</Label>
            <Input
              type="number"
              value={servings || ""}
              onChange={(e) => setServings(Number(e.target.value) || 0)}
              placeholder="—"
              className="w-16 h-8 text-center text-sm border-border/50"
            />
          </div>
        </div>

        {/* Tags */}
        <div className="py-4 border-b border-border">
          <div className="flex flex-wrap items-center gap-2">
            {tags.map((tag) => (
              <Badge key={tag.id} variant="secondary" className="gap-1 pr-1 font-normal">
                {tag.name}
                <button onClick={() => removeTag(tag.id)} className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20">
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
            <Popover open={tagPopoverOpen} onOpenChange={setTagPopoverOpen}>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="sm" className="h-7 gap-1 text-muted-foreground text-xs">
                  <Plus className="h-3.5 w-3.5" />Add tag
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-56 p-0" align="start">
                <Command>
                  <CommandInput placeholder="Search or create..." value={newTagInput} onValueChange={setNewTagInput} />
                  <CommandList>
                    <CommandEmpty>
                      {newTagInput.trim() && (
                        <button onClick={addCustomTag} className="flex w-full items-center gap-2 px-2 py-1.5 text-sm hover:bg-muted">
                          <Plus className="h-3.5 w-3.5" />Create &quot;{newTagInput.trim()}&quot;
                        </button>
                      )}
                    </CommandEmpty>
                    <CommandGroup>
                      {availableTags.filter((at) => !tags.some((t) => t.id === at.id)).map((tag) => (
                        <CommandItem key={tag.id} onSelect={() => { toggleTag(tag); setTagPopoverOpen(false) }}>{tag.name}</CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>
        </div>

        {/* Ingredients & Steps — Tabbed */}
        <div className="mt-6">
          <Tabs defaultValue="ingredients" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="ingredients" className="flex-1">
                Ingredients{ingredients.length > 0 && ` (${ingredients.length})`}
              </TabsTrigger>
              <TabsTrigger value="steps" className="flex-1">
                Steps{steps.length > 0 && ` (${steps.length})`}
              </TabsTrigger>
            </TabsList>

            {/* ── Ingredients Tab ── */}
            <TabsContent value="ingredients" className="mt-4">
              <div className="divide-y divide-border/40">
                {ingredients.map((ingredient, index) => {
                  const prevSection = index > 0 ? ingredients[index - 1].section : null
                  const showSectionHeader = ingredient.section && ingredient.section !== prevSection
                  return (
                    <div key={ingredient.id}>
                      {showSectionHeader && (
                        <div className="pt-2 pb-0.5">
                          <span className="text-xs font-semibold text-foreground/60 uppercase tracking-wider">{ingredient.section}</span>
                        </div>
                      )}
                      <div className="group flex items-center gap-2 py-1.5 -mx-2 px-2 rounded-lg hover:bg-muted/40 transition-colors">
                        {/* Reorder controls */}
                        <div className="flex flex-col items-center opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => moveIngredient(index, "up")} disabled={index === 0} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-20">
                            <ChevronUp className="h-3 w-3" />
                          </button>
                          <button onClick={() => moveIngredient(index, "down")} disabled={index === ingredients.length - 1} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-20">
                            <ChevronDown className="h-3 w-3" />
                          </button>
                        </div>

                        {/* Bullet */}
                        <span className="h-1.5 w-1.5 rounded-full bg-foreground/30 shrink-0" />

                        {/* Ingredient text */}
                        <div className="flex-1 min-w-0">
                          <Input
                            value={ingredient.text}
                            onChange={(e) => updateIngredient(index, { text: e.target.value })}
                            placeholder="e.g., 2 cups cherry tomatoes, halved"
                            className={`border-0 bg-transparent px-1 h-8 focus-visible:ring-0 focus-visible:bg-muted/60 ${errors[`ingredient-${index}`] ? "text-destructive" : ""}`}
                          />
                          {errors[`ingredient-${index}`] && (
                            <p className="mt-0.5 text-xs text-destructive flex items-center gap-1 pl-1">
                              <AlertCircle className="h-3 w-3" />{errors[`ingredient-${index}`]}
                            </p>
                          )}
                        </div>

                        {/* Qty + Unit inline */}
                        <div className="flex items-center gap-1 shrink-0">
                          <Input
                            value={ingredient.quantity}
                            onChange={(e) => updateIngredient(index, { quantity: e.target.value })}
                            placeholder="Qty"
                            className="w-14 h-8 text-center text-sm border-border/50"
                          />
                          <Select value={ingredient.unit} onValueChange={(value) => updateIngredient(index, { unit: value })}>
                            <SelectTrigger className="w-20 h-8 text-sm border-border/50">
                              <SelectValue placeholder="Unit" />
                            </SelectTrigger>
                            <SelectContent>
                              {unitOptions.map((unit) => <SelectItem key={unit} value={unit}>{unit}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Delete */}
                        <button
                          onClick={() => removeIngredient(index)}
                          className="p-1.5 text-muted-foreground/40 hover:text-destructive opacity-0 group-hover:opacity-100 transition-all shrink-0"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>

              <Button variant="ghost" size="sm" onClick={addIngredient} className="mt-3 text-muted-foreground gap-1">
                <Plus className="h-3.5 w-3.5" />Add ingredient
              </Button>
            </TabsContent>

            {/* ── Steps Tab ── */}
            <TabsContent value="steps" className="mt-4">
              <ol className="space-y-4">
                {steps.map((step, index) => (
                  <li key={step.id} className="group flex gap-3">
                    {/* Step number */}
                    <div className="flex flex-col items-center gap-1 pt-1">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                        {index + 1}
                      </span>
                      <div className="flex flex-col opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => moveStep(index, "up")} disabled={index === 0} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-20">
                          <ChevronUp className="h-3 w-3" />
                        </button>
                        <button onClick={() => moveStep(index, "down")} disabled={index === steps.length - 1} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-20">
                          <ChevronDown className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* Step text */}
                    <div className="flex-1 min-w-0">
                      <Textarea
                        value={step.text}
                        onChange={(e) => updateStep(index, { text: e.target.value })}
                        placeholder="Describe this step..."
                        className={`min-h-20 resize-none bg-muted/30 border-0 focus-visible:ring-1 focus-visible:ring-border ${errors[`step-${index}`] ? "ring-1 ring-destructive" : ""}`}
                      />
                      {errors[`step-${index}`] && (
                        <p className="mt-1 text-xs text-destructive flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" />{errors[`step-${index}`]}
                        </p>
                      )}
                    </div>

                    {/* Delete */}
                    <button
                      onClick={() => removeStep(index)}
                      className="p-1.5 text-muted-foreground/40 hover:text-destructive opacity-0 group-hover:opacity-100 transition-all shrink-0 mt-1"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ol>

              <Button variant="ghost" size="sm" onClick={addStep} className="mt-3 text-muted-foreground gap-1">
                <Plus className="h-3.5 w-3.5" />Add step
              </Button>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Unsaved Changes Dialog */}
      <AlertDialog open={showUnsavedDialog} onOpenChange={setShowUnsavedDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsaved changes</AlertDialogTitle>
            <AlertDialogDescription>You have unsaved changes. Are you sure you want to leave? Your changes will be lost.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingNavigation(null)}>Stay</AlertDialogCancel>
            <AlertDialogAction onClick={confirmNavigation}>Leave</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
