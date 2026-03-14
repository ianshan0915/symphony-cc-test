"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Optional ref to the scrollable viewport element */
  viewportRef?: React.RefObject<HTMLDivElement | null>;
}

/**
 * A styled scrollable container with custom scrollbar styles.
 */
const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, children, viewportRef, ...props }, ref) => {
    return (
      <div ref={ref} className={cn("relative overflow-hidden", className)} {...props}>
        <div
          ref={viewportRef}
          className="h-full w-full overflow-y-auto custom-scrollbar"
        >
          {children}
        </div>
      </div>
    );
  }
);
ScrollArea.displayName = "ScrollArea";

export { ScrollArea };
