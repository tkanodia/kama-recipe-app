"use client"

import { useState } from "react"
import { useRouter, useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
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
  AlertCircle,
  AlertTriangle,
  Info,
  Sparkles,
  ExternalLink,
  Loader2,
  ChevronRight,
  RotateCcw,
  Clock,
  Users,
  X,
} from "lucide-react"
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
import { useIngestionJob } from "@/hooks/use-ingestion"
import { useCandidate, useCandidateDecision } from "@/hooks/use-candidates"
import { useTags, useCreateTag } from "@/hooks/use-tags"
import { CandidateReviewSkeleton } from "@/components/skeletons"
import type { CandidateDecisionAction } from "@kama/contracts"

const unitOptions = ["whole", "oz", "lb", "g", "kg", "cup", "cups", "tbsp", "tsp", "ml", "l", "large", "medium", "small", "cloves", "slices", "pieces", "bottle", "can", "bunch", "pinch"]

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

export default function CandidateReviewPage() {
  const router = useRouter()
  const params = useParams()
  const jobId = params.jobId as string

  const { data: job, isLoading: jobLoading } = useIngestionJob(jobId, true)
  const candidateId = job?.candidateId ?? ""
  const { data: candidate, isLoading: candidateLoading, isError, refetch } = useCandidate(candidateId)
  const decision = useCandidateDecision(candidateId)

  const isLoading = jobLoading || candidateLoading

  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [prepTime, setPrepTime] = useState(0)
  const [cookTime, setCookTime] = useState(0)
  const [servings, setServings] = useState(0)
  const [ingredients, setIngredients] = useState<LocalIngredient[]>([])
  const [steps, setSteps] = useState<LocalStep[]>([])
  const [tags, setTags] = useState<string[]>([])
  const [showDiscardDialog, setShowDiscardDialog] = useState(false)
  const [initialized, setInitialized] = useState(false)
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false)
  const [newTagInput, setNewTagInput] = useState("")

  const { data: tagsData } = useTags("recipe")
  const createTagMutation = useCreateTag()
  const availableTags = tagsData?.items ?? []

  if (candidate && !initialized) {
    setTitle(candidate.title)
    setDescription(candidate.description ?? "")
    setPrepTime(candidate.prepTimeMinutes ?? 0)
    setCookTime(candidate.cookTimeMinutes ?? 0)
    setServings(candidate.servings ?? 0)
    setIngredients(candidate.ingredients.map((ing, i) => ({
      id: String(i),
      text: ing.text,
      quantity: ing.quantity ?? "",
      unit: ing.unit ?? "",
      section: (ing as Record<string, unknown>).section as string ?? "",
    })))
    setSteps(candidate.steps.map((s, i) => ({ id: String(i), text: s.text })))
    const rawTags = candidate.recipeTags as Array<string | { id?: string; name?: string }>
    setTags(rawTags.map((t) => typeof t === "string" ? t : (t.name ?? t.id ?? "")))
    setInitialized(true)
  }

  const reviewFindings = candidate?.reviewFindings ?? []
  const unresolvedFindings = reviewFindings.filter((f) => f.severity === "warning" || f.severity === "error")
  const resolvedFindings = reviewFindings.filter((f) => f.severity === "info")

  const updateIngredient = (index: number, updates: Partial<LocalIngredient>) => {
    const updated = [...ingredients]; updated[index] = { ...updated[index], ...updates }; setIngredients(updated)
  }
  const removeIngredient = (index: number) => setIngredients(ingredients.filter((_, i) => i !== index))
  const moveIngredient = (index: number, direction: "up" | "down") => {
    if ((direction === "up" && index === 0) || (direction === "down" && index === ingredients.length - 1)) return
    const ni = direction === "up" ? index - 1 : index + 1
    const updated = [...ingredients]; const [removed] = updated.splice(index, 1); updated.splice(ni, 0, removed); setIngredients(updated)
  }
  const addIngredient = () => setIngredients([...ingredients, { id: Date.now().toString(), text: "", quantity: "", unit: "", section: "" }])

  const updateStep = (index: number, updates: Partial<LocalStep>) => {
    const updated = [...steps]; updated[index] = { ...updated[index], ...updates }; setSteps(updated)
  }
  const removeStep = (index: number) => setSteps(steps.filter((_, i) => i !== index))
  const moveStep = (index: number, direction: "up" | "down") => {
    if ((direction === "up" && index === 0) || (direction === "down" && index === steps.length - 1)) return
    const ni = direction === "up" ? index - 1 : index + 1
    const updated = [...steps]; const [removed] = updated.splice(index, 1); updated.splice(ni, 0, removed); setSteps(updated)
  }
  const addStep = () => setSteps([...steps, { id: Date.now().toString(), text: "" }])

  const removeTag = (tag: string) => setTags((prev) => prev.filter((t) => t !== tag))
  const addTag = (name: string) => {
    if (!name || tags.includes(name)) return
    setTags((prev) => [...prev, name])
  }
  const addCustomTag = () => {
    const trimmed = newTagInput.trim().toLowerCase()
    if (!trimmed || tags.includes(trimmed)) return
    createTagMutation.mutate(
      { domain: "recipe", name: trimmed },
      { onSuccess: (result) => { addTag(result.name); setNewTagInput("") } },
    )
  }

  const handleSave = (action: CandidateDecisionAction) => {
    decision.mutate(
      {
        action,
        editedFields: { title, description, prepTimeMinutes: prepTime, cookTimeMinutes: cookTime, servings, ingredients, steps, recipeTags: tags },
      },
      {
        onSuccess: (result) => {
          if (result.canonicalRecipeId) router.push(`/recipes/${result.canonicalRecipeId}`)
          else if (result.draftRecipeId) router.push(`/drafts/${result.draftRecipeId}`)
          else router.push("/recipes")
        },
      }
    )
  }

  const handleDiscard = () => {
    setShowDiscardDialog(false)
    handleSave("discard")
  }

  const getSeverityIcon = (severity: string) => {
    if (severity === "error") return <AlertCircle className="h-4 w-4 text-destructive" />
    if (severity === "warning") return <AlertTriangle className="h-4 w-4 text-amber-500" />
    return <Info className="h-4 w-4 text-blue-500" />
  }

  if (isLoading || !initialized) {
    return (
      <div className="min-h-screen bg-background">
        <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-foreground" />
              <h1 className="text-lg font-semibold text-foreground">Review Recipe</h1>
            </div>
          </div>
        </div>
        <CandidateReviewSkeleton />
      </div>
    )
  }

  if (isError || !candidate) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-7 w-7 text-destructive" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load candidate</h3>
        <Button variant="outline" className="mt-4" onClick={() => void refetch()}>
          <RotateCcw className="h-4 w-4 mr-1" /> Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background pb-24">
      {/* Header */}
      <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Review Recipe</h1>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* LEFT: Editor */}
          <div className="lg:col-span-2">
            {/* Preview Image */}
            {candidate.previewImageUrl && (
              <div className="relative mb-6 aspect-[21/9] w-full overflow-hidden rounded-xl bg-muted">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={candidate.previewImageUrl} alt="Recipe preview" className="h-full w-full object-cover" />
              </div>
            )}

            {/* Title & Description */}
            <div className="space-y-4">
              <div>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Recipe title"
                  className="text-2xl font-semibold border-0 border-b rounded-none px-0 h-auto py-2 focus-visible:ring-0 focus-visible:border-foreground border-border"
                />
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
                  <Badge key={tag} variant="secondary" className="gap-1 pr-1 font-normal">
                    {tag}
                    <button onClick={() => removeTag(tag)} className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20">
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
                          {availableTags.filter((at) => !tags.includes(at.name)).map((tag) => (
                            <CommandItem key={tag.id} onSelect={() => { addTag(tag.name); setTagPopoverOpen(false) }}>{tag.name}</CommandItem>
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
                                className="border-0 bg-transparent px-1 h-8 focus-visible:ring-0 focus-visible:bg-muted/60"
                              />
                            </div>

                            {/* Qty + Unit inline */}
                            <div className="flex items-center gap-1 shrink-0">
                              <Input
                                value={ingredient.quantity}
                                onChange={(e) => updateIngredient(index, { quantity: e.target.value })}
                                placeholder="Qty"
                                className="w-14 h-8 text-center text-sm border-border/50"
                              />
                              <Select value={ingredient.unit} onValueChange={(v) => updateIngredient(index, { unit: v })}>
                                <SelectTrigger className="w-20 h-8 text-sm border-border/50">
                                  <SelectValue placeholder="Unit" />
                                </SelectTrigger>
                                <SelectContent>
                                  {unitOptions.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}
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
                            className="min-h-20 resize-none bg-muted/30 border-0 focus-visible:ring-1 focus-visible:ring-border"
                          />
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

          {/* RIGHT: Review Context */}
          <div className="space-y-6">
            {candidate.reviewAgentSummary && (
              <Card className="border-0 shadow-sm bg-muted/30">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles className="h-4 w-4 text-foreground" />
                    <span className="text-sm font-medium text-foreground">Review agent summary</span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    AI reviewed this candidate and flagged {unresolvedFindings.length} {unresolvedFindings.length === 1 ? "issue" : "issues"} for your attention.
                  </p>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader><CardTitle className="text-base">Review findings</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {unresolvedFindings.length === 0 && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground"><Check className="h-4 w-4 text-green-600" />No issues — looks good!</div>
                )}
                {unresolvedFindings.map((finding, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg bg-muted/50 p-3">
                    {getSeverityIcon(finding.severity)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground">{finding.message}</p>
                      {finding.field && <p className="mt-1 text-xs text-muted-foreground">{finding.field}</p>}
                    </div>
                  </div>
                ))}
                {resolvedFindings.length > 0 && (
                  <Collapsible>
                    <CollapsibleTrigger className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
                      <ChevronRight className="h-3 w-3" />{resolvedFindings.length} info findings
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-2 space-y-2">
                      {resolvedFindings.map((finding, i) => (
                        <div key={i} className="flex items-start gap-3 rounded-lg p-2 opacity-60">
                          <Check className="h-3.5 w-3.5 text-green-600 mt-0.5" />
                          <p className="text-xs text-muted-foreground">{finding.message}</p>
                        </div>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>
                )}
              </CardContent>
            </Card>

            {candidate.sourceContext && (() => {
              const ctx = candidate.sourceContext as { originalUrl?: string }
              const originalUrl = typeof ctx.originalUrl === "string" ? ctx.originalUrl : undefined
              const src = (candidate.fieldProvenanceMap as Record<string, unknown> | undefined)?._source as { socialUrl?: string; discoveredUrl?: string; extractionMethod?: string } | undefined
              return (
                <Card>
                  <CardHeader><CardTitle className="text-base">Source</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-start gap-3 rounded-lg bg-muted/50 p-3">
                      <ExternalLink className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground">Source asset: {candidate.sourceAssetId}</p>
                        {originalUrl && (
                          <a href={originalUrl} target="_blank" rel="noopener noreferrer" className="mt-1 block text-xs text-primary hover:underline truncate">
                            {originalUrl}
                          </a>
                        )}
                        {src?.discoveredUrl && (
                          <div className="mt-2 pt-2 border-t border-border/50">
                            <p className="text-xs text-muted-foreground">Recipe extracted from</p>
                            <a href={src.discoveredUrl} target="_blank" rel="noopener noreferrer" className="mt-0.5 block text-xs text-primary hover:underline truncate">
                              {src.discoveredUrl}
                            </a>
                          </div>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Extraction method: {candidate.selectedExtractionMethod}
                    </p>
                  </CardContent>
                </Card>
              )
            })()}
          </div>
        </div>
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-50">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Button variant="ghost" className="text-muted-foreground hover:text-destructive" onClick={() => setShowDiscardDialog(true)} disabled={decision.isPending}>
            Discard
          </Button>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => handleSave("save_draft")} disabled={decision.isPending || !candidate.draftEligible}>
              {decision.isPending ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</> : "Save as draft"}
            </Button>
            <Button onClick={() => handleSave("save_canonical")} disabled={decision.isPending || !candidate.canonicalEligible}>
              {decision.isPending ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</> : "Save as trusted recipe"}
            </Button>
          </div>
        </div>
      </div>

      <AlertDialog open={showDiscardDialog} onOpenChange={setShowDiscardDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard this recipe?</AlertDialogTitle>
            <AlertDialogDescription>This extracted recipe will be permanently discarded. You can always re-submit the source to try again.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep reviewing</AlertDialogCancel>
            <AlertDialogAction onClick={handleDiscard} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Discard</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
