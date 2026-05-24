"use client"

import { useState, useEffect, useMemo } from "react"
import Link from "next/link"
import { useRouter, useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  Plus,
  Trash2,
  ChevronUp,
  ChevronDown,
  Check,
  ChevronsUpDown,
  Loader2,
  FileEdit,
  ArrowRight,
  RotateCcw,
  AlertCircle,
} from "lucide-react"
import { useDraft, useUpdateDraft, useDeleteDraft } from "@/hooks/use-drafts"
import { useTags } from "@/hooks/use-tags"
import { useIngredientSearch } from "@/hooks/use-ingredients"
import { DraftDetailSkeleton } from "@/components/skeletons"

const unitOptions = ["whole", "oz", "lb", "g", "kg", "cup", "cups", "tbsp", "tsp", "ml", "l", "large", "medium", "small", "cloves", "slices", "pieces", "bottle", "can", "bunch", "pinch"]

type LocalIngredient = {
  id: string
  text: string
  quantity: string
  unit: string
  section: string
  mappedIngredient: { id: string; name: string } | null
}

type LocalStep = {
  id: string
  text: string
}

export default function DraftDetailPage() {
  const router = useRouter()
  const params = useParams()
  const draftId = params.id as string

  const { data: draft, isLoading, isError, refetch } = useDraft(draftId)
  const updateDraft = useUpdateDraft(draftId)
  const deleteDraft = useDeleteDraft(draftId)
  const { data: tagsData } = useTags("recipe")
  const availableTags = useMemo(() => tagsData?.items?.map((t) => t.name) ?? [], [tagsData])

  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [prepTime, setPrepTime] = useState(0)
  const [cookTime, setCookTime] = useState(0)
  const [servings, setServings] = useState(0)
  const [tags, setTags] = useState<string[]>([])
  const [ingredients, setIngredients] = useState<LocalIngredient[]>([])
  const [steps, setSteps] = useState<LocalStep[]>([])

  const [initialized, setInitialized] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  useEffect(() => {
    if (draft && !initialized) {
      const d = draft as Record<string, unknown>
      setTitle((d.title as string) ?? "")
      setDescription((d.description as string) ?? "")
      setPrepTime((d.prepTimeMinutes as number) ?? 0)
      setCookTime((d.cookTimeMinutes as number) ?? 0)
      setServings((d.servings as number) ?? 0)

      const rawTags = (d.recipeTags ?? []) as string[]
      setTags(rawTags)

      const rawIngs = (d.ingredients ?? []) as Array<Record<string, unknown>>
      setIngredients(rawIngs.map((ing, i) => ({
        id: String(i),
        text: (ing.text as string) ?? "",
        quantity: (ing.quantity as string) ?? "",
        unit: (ing.unit as string) ?? "",
        section: (ing.section as string) ?? "",
        mappedIngredient: ing.ingredientId ? { id: ing.ingredientId as string, name: "" } : null,
      })))

      const rawSteps = (d.steps ?? []) as Array<Record<string, unknown>>
      setSteps(rawSteps.map((s, i) => ({
        id: String(i),
        text: (s.text as string) ?? "",
      })))

      setInitialized(true)
    }
  }, [draft, initialized])

  useEffect(() => {
    if (initialized) setIsDirty(true)
  }, [title, description, prepTime, cookTime, servings, tags, ingredients, steps, initialized])

  const isPromotionEligible = title.trim().length > 0 && description.trim().length > 0 && ingredients.length > 0 && steps.length > 0
  const missingForPromotion: string[] = []
  if (!title.trim()) missingForPromotion.push("title")
  if (!description.trim()) missingForPromotion.push("description")
  if (ingredients.length === 0) missingForPromotion.push("at least one ingredient")
  if (steps.length === 0) missingForPromotion.push("at least one step")

  const handleSave = () => {
    updateDraft.mutate(
      {
        title, description, prepTimeMinutes: prepTime, cookTimeMinutes: cookTime,
        servings, recipeTags: tags,
        ingredients: ingredients.map((ing) => ({ text: ing.text, quantity: ing.quantity, unit: ing.unit, section: ing.section || undefined, ingredientId: ing.mappedIngredient?.id })),
        steps: steps.map((s, i) => ({ order: i + 1, text: s.text })),
      },
      { onSuccess: () => setIsDirty(false) }
    )
  }

  const handleDelete = () => {
    setShowDeleteDialog(false)
    deleteDraft.mutate(undefined, {
      onSuccess: () => router.push("/recipes"),
    })
  }

  const updateIngredient = (index: number, updates: Partial<LocalIngredient>) => {
    const updated = [...ingredients]; updated[index] = { ...updated[index], ...updates }; setIngredients(updated)
  }
  const removeIngredient = (index: number) => setIngredients(ingredients.filter((_, i) => i !== index))
  const moveIngredient = (index: number, dir: "up" | "down") => {
    if ((dir === "up" && index === 0) || (dir === "down" && index === ingredients.length - 1)) return
    const ni = dir === "up" ? index - 1 : index + 1; const u = [...ingredients]; const [r] = u.splice(index, 1); u.splice(ni, 0, r); setIngredients(u)
  }
  const addIngredient = () => setIngredients([...ingredients, { id: Date.now().toString(), text: "", quantity: "", unit: "", section: "", mappedIngredient: null }])

  const updateStep = (index: number, updates: Partial<LocalStep>) => {
    const updated = [...steps]; updated[index] = { ...updated[index], ...updates }; setSteps(updated)
  }
  const removeStep = (index: number) => setSteps(steps.filter((_, i) => i !== index))
  const moveStep = (index: number, dir: "up" | "down") => {
    if ((dir === "up" && index === 0) || (dir === "down" && index === steps.length - 1)) return
    const ni = dir === "up" ? index - 1 : index + 1; const u = [...steps]; const [r] = u.splice(index, 1); u.splice(ni, 0, r); setSteps(u)
  }
  const addStep = () => setSteps([...steps, { id: Date.now().toString(), text: "" }])

  const toggleTag = (tag: string) => setTags((p) => p.includes(tag) ? p.filter((t) => t !== tag) : [...p, tag])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <FileEdit className="h-5 w-5 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">Draft</h1>
            </div>
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
        <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load draft</h3>
        <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
          <RotateCcw className="h-4 w-4 mr-1" /> Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <FileEdit className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Draft</h1>
            {isDirty && <Badge variant="secondary" className="text-xs">Unsaved changes</Badge>}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-destructive" onClick={() => setShowDeleteDialog(true)}>
              <Trash2 className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={handleSave} disabled={!isDirty || updateDraft.isPending}>
              {updateDraft.isPending ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</> : "Save"}
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-4 py-6">
        {/* Promotion Banner */}
        <Card className={`border-0 shadow-sm ${isPromotionEligible ? "bg-green-50 dark:bg-green-950/20" : "bg-amber-50 dark:bg-amber-950/20"}`}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-foreground">
                  {isPromotionEligible ? "Ready to save as a trusted recipe" : "This is a draft — complete the required fields to save as a trusted recipe."}
                </p>
                {!isPromotionEligible && missingForPromotion.length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">Missing: {missingForPromotion.join(", ")}</p>
                )}
              </div>
              <Button size="sm" disabled={!isPromotionEligible} asChild={isPromotionEligible}>
                {isPromotionEligible ? (
                  <Link href={`/drafts/${draftId}/promote`}>Review for trusted save<ArrowRight className="h-4 w-4 ml-1" /></Link>
                ) : (
                  <span>Review for trusted save<ArrowRight className="h-4 w-4 ml-1" /></span>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="mt-6 space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Title</CardTitle></CardHeader>
            <CardContent><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Recipe title" /></CardContent>
          </Card>

          <Card className={!description.trim() ? "ring-1 ring-amber-300 dark:ring-amber-700" : ""}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Description</CardTitle>
                {!description.trim() && <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">Needed for promotion</Badge>}
              </div>
            </CardHeader>
            <CardContent><Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="A brief description (1-2 sentences)" className="min-h-20 resize-none" /></CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Time & Servings</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div><Label className="text-sm text-muted-foreground">Prep Time (min)</Label><Input type="number" value={prepTime || ""} onChange={(e) => setPrepTime(Number(e.target.value) || 0)} className="mt-1.5" /></div>
                <div><Label className="text-sm text-muted-foreground">Cook Time (min)</Label><Input type="number" value={cookTime || ""} onChange={(e) => setCookTime(Number(e.target.value) || 0)} className="mt-1.5" /></div>
                <div><Label className="text-sm text-muted-foreground">Servings</Label><Input type="number" value={servings || ""} onChange={(e) => setServings(Number(e.target.value) || 0)} className="mt-1.5" /></div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Tags</CardTitle></CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {availableTags.map((tag) => (
                  <Badge key={tag} variant={tags.includes(tag) ? "default" : "outline"} className="cursor-pointer font-normal" onClick={() => toggleTag(tag)}>{tag}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Ingredients</CardTitle>
                <Button variant="outline" size="sm" onClick={addIngredient}><Plus className="h-4 w-4 mr-1" /> Add</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {ingredients.map((ingredient, index) => {
                  const prevSection = index > 0 ? ingredients[index - 1].section : null
                  const showSectionHeader = ingredient.section && ingredient.section !== prevSection
                  return (
                    <div key={ingredient.id}>
                      {showSectionHeader && (
                        <div className="pt-2 pb-1 mb-1 border-b border-border/50">
                          <span className="text-xs font-semibold text-foreground/70 uppercase tracking-wide">{ingredient.section}</span>
                        </div>
                      )}
                      <div className="group rounded-lg border border-border p-3">
                        <div className="flex items-start gap-2">
                          <div className="flex flex-col items-center gap-0.5 pt-2">
                            <button onClick={() => moveIngredient(index, "up")} disabled={index === 0} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronUp className="h-3 w-3" /></button>
                            <button onClick={() => moveIngredient(index, "down")} disabled={index === ingredients.length - 1} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronDown className="h-3 w-3" /></button>
                          </div>
                          <div className="flex-1 space-y-2">
                            <Input value={ingredient.text} onChange={(e) => updateIngredient(index, { text: e.target.value })} placeholder="e.g., 2 cups cherry tomatoes" className="text-sm" />
                            <div className="grid grid-cols-3 gap-2">
                              <div><Label className="text-xs text-muted-foreground">Qty</Label><Input value={ingredient.quantity} onChange={(e) => updateIngredient(index, { quantity: e.target.value })} className="mt-1 text-sm" /></div>
                              <div><Label className="text-xs text-muted-foreground">Unit</Label>
                                <Select value={ingredient.unit} onValueChange={(v) => updateIngredient(index, { unit: v })}>
                                  <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Unit" /></SelectTrigger>
                                  <SelectContent>{unitOptions.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                                </Select>
                              </div>
                              <div><Label className="text-xs text-muted-foreground">Mapped</Label>
                                <IngredientCombobox value={ingredient.mappedIngredient} onChange={(m) => updateIngredient(index, { mappedIngredient: m })} />
                              </div>
                            </div>
                          </div>
                          <button onClick={() => removeIngredient(index)} className="p-1 text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Steps</CardTitle>
                <Button variant="outline" size="sm" onClick={addStep}><Plus className="h-4 w-4 mr-1" /> Add Step</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {steps.map((step, index) => (
                <div key={step.id} className="group flex gap-3">
                  <div className="flex flex-col items-center gap-1 pt-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-sm font-medium text-background">{index + 1}</span>
                    <div className="flex flex-col opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => moveStep(index, "up")} disabled={index === 0} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronUp className="h-3 w-3" /></button>
                      <button onClick={() => moveStep(index, "down")} disabled={index === steps.length - 1} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronDown className="h-3 w-3" /></button>
                    </div>
                  </div>
                  <div className="flex-1">
                    <Textarea value={step.text} onChange={(e) => updateStep(index, { text: e.target.value })} placeholder="Describe this step..." className="min-h-20 resize-none border-0 bg-muted/50 focus-visible:ring-1 text-sm" />
                  </div>
                  <button onClick={() => removeStep(index)} className="p-1 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this draft?</AlertDialogTitle>
            <AlertDialogDescription>This draft will be permanently deleted. This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function IngredientCombobox({ value, onChange }: { value: { id: string; name: string } | null; onChange: (v: { id: string; name: string } | null) => void }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")
  const { data: searchResults } = useIngredientSearch(search)
  const items = searchResults?.items ?? []

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="mt-1 w-full justify-between font-normal text-sm">
          {value ? value.name : "Select..."}<ChevronsUpDown className="ml-2 h-3 w-3 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search..." value={search} onValueChange={setSearch} />
          <CommandList>
            <CommandEmpty>{search.trim() && <button onClick={() => { onChange({ id: `custom-${Date.now()}`, name: search.trim() }); setSearch(""); setOpen(false) }} className="flex w-full items-center gap-2 px-2 py-1.5 text-sm hover:bg-muted"><Plus className="h-4 w-4" /> Create &quot;{search.trim()}&quot;</button>}</CommandEmpty>
            <CommandGroup>{items.map((i) => <CommandItem key={i.id} onSelect={() => { onChange({ id: i.id, name: i.name }); setOpen(false) }}><Check className={`mr-2 h-4 w-4 ${value?.id === i.id ? "opacity-100" : "opacity-0"}`} />{i.name}</CommandItem>)}</CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
