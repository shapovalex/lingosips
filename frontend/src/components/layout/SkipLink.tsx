/**
 * SkipLink — visually hidden "Skip to main content" link for keyboard navigation.
 * Must be the FIRST focusable element in the DOM (renders before the main layout).
 * Becomes visible only on :focus (WCAG 2.1 AA).
 */
export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-4 focus:left-4
                 focus:px-4 focus:py-2 focus:bg-indigo-500 focus:text-white focus:rounded-md
                 focus:font-medium focus:text-sm"
    >
      Skip to main content
    </a>
  )
}
