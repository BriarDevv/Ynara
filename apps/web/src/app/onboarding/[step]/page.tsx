import { notFound } from "next/navigation";
import { ONBOARDING_STEPS, type OnboardingStep } from "@/features/onboarding/constants";
import { StepRouter } from "./StepRouter";

export const dynamic = "force-dynamic";

export default async function OnboardingStepPage({
  params,
}: {
  params: Promise<{ step: string }>;
}) {
  const { step } = await params;
  if (!isOnboardingStep(step)) notFound();
  return <StepRouter step={step} />;
}

function isOnboardingStep(value: string): value is OnboardingStep {
  return (ONBOARDING_STEPS as readonly string[]).includes(value);
}
