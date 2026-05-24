import { SignUp } from "@clerk/nextjs";

import { isClerkEnabled } from "@/lib/clerk";

export default function SignUpPage() {
  if (!isClerkEnabled()) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center text-stone-400 text-sm">
        Clerk is not configured. Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY in apps/web/.env.local
      </div>
    );
  }
  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <SignUp routing="path" path="/sign-up" />
    </div>
  );
}
