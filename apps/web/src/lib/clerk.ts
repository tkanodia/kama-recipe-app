/** True when Clerk keys are configured (not placeholder / empty). */
export function isClerkEnabled(): boolean {
  const pk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";
  return pk.length > 0 && !pk.includes("placeholder");
}
