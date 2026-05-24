"use client"

import { useState, useRef, useCallback } from "react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Link2,
  ImageIcon,
  FileText,
  Upload,
  X,
  Loader2,
  AlertCircle,
  Sparkles,
  ArrowRight,
  ClipboardPaste,
  BrainCircuit,
} from "lucide-react"
import { useSubmitIngestion } from "@/hooks/use-ingestion"
import { usePresignedUrl } from "@/hooks/use-media"
import type { SubmitIngestionRequest } from "@kama/contracts"

type SourceType = "url" | "image" | "text"

const LLM_MODELS = [
  { slug: "gpt-4o", label: "GPT-4o", provider: "OpenAI" },
  { slug: "gpt-4o-mini", label: "GPT-4o Mini", provider: "OpenAI" },
  { slug: "claude-opus-4-20250514", label: "Claude Opus 4", provider: "Anthropic" },
  { slug: "claude-sonnet-4-20250514", label: "Claude Sonnet 4", provider: "Anthropic" },
] as const

export default function IngestPage() {
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<SourceType>("url")
  const [urlInput, setUrlInput] = useState("")
  const [textInput, setTextInput] = useState("")
  const [contextNote, setContextNote] = useState("")
  const [selectedModel, setSelectedModel] = useState<string>("gpt-4o-mini")
  const [uploadedImage, setUploadedImage] = useState<{
    file: File
    preview: string
  } | null>(null)

  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const submitIngestion = useSubmitIngestion()
  const presignedUrl = usePresignedUrl()

  const isSubmitting = submitIngestion.isPending || isUploading

  const canSubmit =
    !isSubmitting &&
    ((activeTab === "url" && urlInput.trim().length > 0) ||
      (activeTab === "image" && uploadedImage !== null) ||
      (activeTab === "text" && textInput.trim().length > 0))

  const handleTabChange = (tab: string) => {
    setActiveTab(tab as SourceType)
    setError(null)
  }

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text) setUrlInput(text.trim())
    } catch {
      /* clipboard not available */
    }
  }

  const handleImageSelect = (file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Please select an image file")
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Image must be less than 10MB")
      return
    }
    setError(null)
    setUploadedImage({ file, preview: URL.createObjectURL(file) })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleImageSelect(file)
  }

  const removeImage = () => {
    if (uploadedImage) URL.revokeObjectURL(uploadedImage.preview)
    setUploadedImage(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragging(true) }, [])
  const handleDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragging(false) }, [])
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleImageSelect(file)
  }, [])

  const handleSubmit = async () => {
    setError(null)

    try {
      let fileAssetRef: string | undefined

      if (activeTab === "image" && uploadedImage) {
        setIsUploading(true)
        const presigned = await presignedUrl.mutateAsync({
          fileName: uploadedImage.file.name,
          contentType: uploadedImage.file.type,
          context: "source_upload",
        })

        await fetch(presigned.uploadUrl, {
          method: "PUT",
          body: uploadedImage.file,
          headers: { "Content-Type": uploadedImage.file.type },
        })

        fileAssetRef = presigned.assetRef
        setIsUploading(false)
      }

      const body: SubmitIngestionRequest = {
        sourceType: activeTab,
        ...(activeTab === "url" && { url: urlInput }),
        ...(activeTab === "image" && { fileAssetRef }),
        ...(activeTab === "text" && { rawTextInput: textInput }),
        ...(contextNote.trim() && { contextNote: contextNote.trim() }),
      }

      const result = await submitIngestion.mutateAsync(body)
      router.push(`/ingest/${result.ingestionJobId}`)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong. Please try again."
      setError(message)
      setIsUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-2xl items-center px-4">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Add Recipe</h1>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Where&apos;s the recipe?</h2>
          <p className="mt-2 text-muted-foreground">
            Paste a link, upload a photo, or type it in. We&apos;ll extract and structure everything for you.
          </p>
        </div>

        <Card className="border-0 shadow-lg">
          <CardContent className="p-6">
            <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
              <TabsList className="w-full">
                <TabsTrigger value="url" className="flex-1 gap-2"><Link2 className="h-4 w-4" />URL</TabsTrigger>
                <TabsTrigger value="image" className="flex-1 gap-2"><ImageIcon className="h-4 w-4" />Image</TabsTrigger>
                <TabsTrigger value="text" className="flex-1 gap-2"><FileText className="h-4 w-4" />Text</TabsTrigger>
              </TabsList>

              {/* URL Tab */}
              <TabsContent value="url" className="mt-6">
                <div className="space-y-4">
                  <div>
                    <Label className="text-sm text-muted-foreground">Recipe URL</Label>
                    <div className="relative mt-1.5">
                      <Input
                        value={urlInput}
                        onChange={(e) => { setUrlInput(e.target.value); setError(null) }}
                        placeholder="https://www.bonappetit.com/recipe/..."
                        className="pr-10"
                      />
                      <button onClick={handlePaste} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground transition-colors" title="Paste from clipboard">
                        <ClipboardPaste className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">Works with recipe blogs, YouTube, Instagram, TikTok, and most cooking sites.</p>
                  </div>
                </div>
              </TabsContent>

              {/* Image Tab */}
              <TabsContent value="image" className="mt-6">
                <div className="space-y-4">
                  {uploadedImage ? (
                    <div className="relative">
                      <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-muted">
                        <Image src={uploadedImage.preview} alt="Uploaded recipe" fill className="object-contain" />
                      </div>
                      <button onClick={removeImage} className="absolute top-2 right-2 flex h-7 w-7 items-center justify-center rounded-full bg-background/80 text-foreground backdrop-blur hover:bg-background transition-colors">
                        <X className="h-4 w-4" />
                      </button>
                      <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                        <ImageIcon className="h-4 w-4" />
                        {uploadedImage.file.name}
                        <Badge variant="secondary" className="font-normal">{(uploadedImage.file.size / 1024 / 1024).toFixed(1)} MB</Badge>
                      </div>
                    </div>
                  ) : (
                    <div
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onDrop={handleDrop}
                      onClick={() => fileInputRef.current?.click()}
                      className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 transition-colors ${isDragging ? "border-foreground bg-muted/80" : "border-border hover:border-foreground/30 hover:bg-muted/50"}`}
                    >
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                        <Upload className="h-5 w-5 text-muted-foreground" />
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-foreground">{isDragging ? "Drop your image here" : "Click to upload or drag and drop"}</p>
                        <p className="mt-1 text-xs text-muted-foreground">Cookbook pages, screenshots, handwritten recipe cards. PNG, JPG up to 10MB.</p>
                      </div>
                      <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
                    </div>
                  )}

                  {isUploading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />Uploading image...
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Text Tab */}
              <TabsContent value="text" className="mt-6">
                <div className="space-y-4">
                  <div>
                    <Label className="text-sm text-muted-foreground">Recipe text</Label>
                    <Textarea
                      value={textInput}
                      onChange={(e) => { setTextInput(e.target.value); setError(null) }}
                      placeholder="Paste or type the recipe here — ingredients, steps, notes, anything you have..."
                      className="mt-1.5 min-h-48 resize-none border-0 bg-muted/50 focus-visible:ring-1"
                    />
                    <p className="mt-2 text-xs text-muted-foreground">Messy is fine — we&apos;ll structure it for you. Copy-paste from a message, email, or note.</p>
                  </div>
                </div>
              </TabsContent>

              {/* Context Note */}
              <div className="mt-6 pt-6 border-t border-border">
                <Label className="text-sm text-muted-foreground">
                  Context note <span className="text-muted-foreground/60">(optional)</span>
                </Label>
                <Input value={contextNote} onChange={(e) => setContextNote(e.target.value)} placeholder="e.g., This is from my grandmother's cookbook, page 42" className="mt-1.5" />
              </div>

              {/* Model Picker */}
              <div className="mt-4">
                <Label className="text-sm text-muted-foreground flex items-center gap-1.5">
                  <BrainCircuit className="h-3.5 w-3.5" />Extraction model
                </Label>
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger className="mt-1.5 w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {LLM_MODELS.map((m) => (
                      <SelectItem key={m.slug} value={m.slug}>
                        <span className="flex items-center gap-2">
                          {m.label}
                          <span className="text-xs text-muted-foreground">{m.provider}</span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Error */}
              {error && (
                <div className="mt-4 flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0" />{error}
                </div>
              )}

              {/* Submit */}
              <div className="mt-6">
                <Button onClick={handleSubmit} disabled={!canSubmit} className="w-full" size="lg">
                  {isSubmitting ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{isUploading ? "Uploading..." : "Submitting..."}</>
                  ) : (
                    <>Extract Recipe<ArrowRight className="h-4 w-4 ml-2" /></>
                  )}
                </Button>
              </div>
            </Tabs>
          </CardContent>
        </Card>

        <div className="mt-8 text-center">
          <p className="text-xs text-muted-foreground">
            Supports recipe blogs, YouTube, Instagram, TikTok, Facebook, cookbook photos, screenshots, and handwritten recipe cards.
          </p>
        </div>
      </div>
    </div>
  )
}
