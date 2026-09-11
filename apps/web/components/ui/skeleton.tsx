import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Loading placeholder that mirrors real content dimensions rather than a
 * spinner (DESIGN-SYSTEM.md §4: "Skeleton matching final layout — never a
 * centred spinner on a full page, which causes layout shift").
 */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />
}

export { Skeleton }
