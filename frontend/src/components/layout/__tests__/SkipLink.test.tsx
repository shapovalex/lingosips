import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { SkipLink } from "@/components/layout"

describe("SkipLink", () => {
  it("renders with correct href pointing to main content", () => {
    render(<SkipLink />)
    const link = screen.getByRole("link", { name: /skip to main content/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "#main-content")
  })

  it("has sr-only class by default (visually hidden)", () => {
    render(<SkipLink />)
    const link = screen.getByRole("link", { name: /skip to main content/i })
    expect(link.className).toContain("sr-only")
  })

  it("contains the correct accessible text", () => {
    render(<SkipLink />)
    expect(screen.getByText("Skip to main content")).toBeInTheDocument()
  })

  it("has focus-visible classes to become visible on focus", () => {
    render(<SkipLink />)
    const link = screen.getByRole("link", { name: /skip to main content/i })
    // Verify the focus classes are present in the className
    expect(link.className).toContain("focus:not-sr-only")
    expect(link.className).toContain("focus:absolute")
    expect(link.className).toContain("focus:bg-indigo-500")
  })
})
