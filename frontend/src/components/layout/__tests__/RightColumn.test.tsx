import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { RightColumn } from "@/components/layout"

/**
 * RightColumn renders two sections:
 *  - Desktop aside (always in DOM — shows children regardless of state)
 *  - Mobile accordion (state-driven — data-testid="right-column-mobile-body" only when expanded)
 *
 * jsdom does not process CSS, so both desktop and mobile markup are always present.
 * Tests use data-testid="right-column-mobile-body" to test the state machine behavior.
 */
describe("RightColumn", () => {
  describe("state: expanded", () => {
    it("shows mobile content body when expanded", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>Queue Content</div></RightColumn>)

      // Default is collapsed — click toggle to expand
      const toggleBtn = screen.getByRole("button")
      await user.click(toggleBtn)

      expect(screen.getByTestId("right-column-mobile-body")).toBeInTheDocument()
    })

    it("shows the toggle button when expanded", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>content</div></RightColumn>)
      const toggleBtn = screen.getByRole("button")
      await user.click(toggleBtn)
      expect(toggleBtn).toBeInTheDocument()
    })

    it("toggle button shows 'Close' text when expanded", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>content</div></RightColumn>)
      const toggleBtn = screen.getByRole("button")
      await user.click(toggleBtn)
      expect(toggleBtn.textContent).toContain("Close")
    })
  })

  describe("state: collapsed (default)", () => {
    it("hides mobile content body in collapsed state (data-testid absent)", () => {
      render(<RightColumn><div>Queue Content</div></RightColumn>)
      // Mobile accordion body is NOT rendered when collapsed
      expect(screen.queryByTestId("right-column-mobile-body")).not.toBeInTheDocument()
    })

    it("shows toggle button in collapsed state", () => {
      render(<RightColumn><div>content</div></RightColumn>)
      expect(screen.getByRole("button")).toBeInTheDocument()
    })

    it("toggle button shows 'Cards due' text when collapsed", () => {
      render(<RightColumn><div>content</div></RightColumn>)
      const toggleBtn = screen.getByRole("button")
      expect(toggleBtn.textContent).toContain("Cards due")
    })
  })

  describe("state machine transitions", () => {
    it("toggles from collapsed to expanded on button click", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>Queue Content</div></RightColumn>)

      // Start collapsed — no mobile body
      expect(screen.queryByTestId("right-column-mobile-body")).not.toBeInTheDocument()

      // Toggle to expanded — mobile body appears
      await user.click(screen.getByRole("button"))
      expect(screen.getByTestId("right-column-mobile-body")).toBeInTheDocument()
    })

    it("toggles from expanded back to collapsed on second click", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>Queue Content</div></RightColumn>)

      const toggleBtn = screen.getByRole("button")
      // Expand
      await user.click(toggleBtn)
      expect(screen.getByTestId("right-column-mobile-body")).toBeInTheDocument()

      // Collapse
      await user.click(toggleBtn)
      expect(screen.queryByTestId("right-column-mobile-body")).not.toBeInTheDocument()
    })

    it("toggle button text changes between collapsed and expanded", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>content</div></RightColumn>)

      const toggleBtn = screen.getByRole("button")
      // Collapsed state
      expect(toggleBtn.textContent).toContain("Cards due")

      // Expanded state
      await user.click(toggleBtn)
      expect(toggleBtn.textContent).toContain("Close")
    })

    it("aria-expanded attribute reflects state", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>content</div></RightColumn>)

      const toggleBtn = screen.getByRole("button")
      expect(toggleBtn).toHaveAttribute("aria-expanded", "false")

      await user.click(toggleBtn)
      expect(toggleBtn).toHaveAttribute("aria-expanded", "true")
    })

    it("toggle button has aria-controls pointing to expandable region", () => {
      render(<RightColumn><div>content</div></RightColumn>)
      const toggleBtn = screen.getByRole("button")
      expect(toggleBtn).toHaveAttribute("aria-controls", "right-column-mobile-content")
    })

    it("expanded content has id matching aria-controls", async () => {
      const user = userEvent.setup()
      render(<RightColumn><div>content</div></RightColumn>)
      await user.click(screen.getByRole("button"))
      const content = screen.getByTestId("right-column-mobile-body")
      expect(content).toHaveAttribute("id", "right-column-mobile-content")
    })
  })
})
