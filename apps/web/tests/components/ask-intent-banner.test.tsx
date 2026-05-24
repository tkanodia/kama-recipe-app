import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { AskIntentBanner } from "@/components/search/ask-intent-banner"

describe("AskIntentBanner", () => {
  it("links to Ask with the encoded query", () => {
    render(<AskIntentBanner query="what can I make with chicken?" />)

    const link = screen.getByRole("link", { name: /try asking kama/i })
    expect(link).toHaveAttribute(
      "href",
      "/ask?q=what%20can%20I%20make%20with%20chicken%3F",
    )
  })
})
