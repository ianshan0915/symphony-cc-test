import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with proper conflict resolution.
 *
 * Combines `clsx` (conditional class joining) with `tailwind-merge`
 * (deduplication of conflicting Tailwind utilities).
 *
 * @example
 * cn("px-2 py-1", condition && "px-4") // "py-1 px-4" when condition is true
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
