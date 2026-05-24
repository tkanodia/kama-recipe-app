import type { LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"

interface EmptyStateAction {
  label: string
  href?: string
  onClick?: () => void
  variant?: "default" | "outline" | "ghost"
  icon?: LucideIcon
}

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  action?: EmptyStateAction
  secondaryAction?: EmptyStateAction
  className?: string
}

function ActionButton({ action }: { action: EmptyStateAction }) {
  const Icon = action.icon
  const btn = (
    <Button
      variant={action.variant ?? "default"}
      className="mt-4"
      onClick={action.onClick}
    >
      {Icon && <Icon className="h-4 w-4 mr-1" />}
      {action.label}
    </Button>
  )

  if (action.href) {
    return (
      <Button variant={action.variant ?? "default"} className="mt-4" asChild>
        <Link href={action.href}>
          {Icon && <Icon className="h-4 w-4 mr-1" />}
          {action.label}
        </Link>
      </Button>
    )
  }

  return btn
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center py-20 text-center ${className}`}>
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
      <div className="flex items-center gap-3">
        {action && <ActionButton action={action} />}
        {secondaryAction && <ActionButton action={secondaryAction} />}
      </div>
    </div>
  )
}
