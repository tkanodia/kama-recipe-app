import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { isClerkEnabled } from "@/lib/clerk";

export default async function HomePage() {
  if (!isClerkEnabled()) {
    redirect("/recipes");
  }
  const session = await auth();
  if (session.userId) {
    redirect("/recipes");
  }
  redirect("/sign-in");
}
