import { redirect } from "next/navigation";

/**
 * /onboarding sin step → redirect a /onboarding/auth (primer step).
 * El layout se encarga de redirect a /hoy si el user ya completó.
 */
export default function OnboardingIndexPage() {
  redirect("/onboarding/auth");
}
