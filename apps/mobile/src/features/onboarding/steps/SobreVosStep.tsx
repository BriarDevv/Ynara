import type { Dedication } from "@ynara/core/features/onboarding";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";
import { cn } from "@/lib/cn";
import { useOnboardingStore } from "@/stores/onboarding";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../useOnboardingNav";

const DEDICATION_OPTIONS: readonly { value: Dedication; label: string }[] = [
  { value: "estudio", label: "Estudio" },
  { value: "trabajo", label: "Trabajo" },
  { value: "ambos", label: "Ambos" },
  { value: "otro", label: "Otro" },
];

/**
 * Step "Sobre vos" del onboarding: contexto para que Ynara te conozca y lo
 * recuerde (a qué te dedicás, qué estudiás/trabajás, para qué la usás, qué te
 * interesa). Opcional — podés dejar todo en blanco y "Continuar". Guarda en el
 * draft de onboarding de core (`setProfileContext`), igual que web; al completar,
 * el draft se vuelca al user store. Va después de "modos" y antes de "accesibilidad".
 */
export function SobreVosStep() {
  const { back, next } = useOnboardingNav();
  const draft = useOnboardingStore.getState();
  const setProfileContext = useOnboardingStore((s) => s.setProfileContext);
  const copy = STEP_COPY["sobre-vos"];

  const [dedication, setDedication] = useState<Dedication | null>(draft.dedication);
  const [studyWhat, setStudyWhat] = useState(draft.studyWhat);
  const [workWhat, setWorkWhat] = useState(draft.workWhat);
  const [purpose, setPurpose] = useState(draft.purpose);
  const [interests, setInterests] = useState(draft.interests);

  const showStudy = dedication === "estudio" || dedication === "ambos";
  const showWork = dedication === "trabajo" || dedication === "ambos";

  const onNext = () => {
    setProfileContext({
      dedication,
      studyWhat: studyWhat.trim(),
      workWhat: workWhat.trim(),
      purpose: purpose.trim(),
      interests: interests.trim(),
    });
    next();
  };

  return (
    <StepShell
      eyebrow={copy.eyebrow}
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={onNext} nextLabel="Continuar" />}
    >
      <View className="gap-3">
        <Text className="text-caption text-ink-soft">¿A QUÉ TE DEDICÁS?</Text>
        <View className="flex-row flex-wrap gap-2">
          {DEDICATION_OPTIONS.map((opt) => {
            const selected = dedication === opt.value;
            return (
              <Pressable
                key={opt.value}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                onPress={() => setDedication(opt.value)}
                hitSlop={6}
                className={cn(
                  "rounded-pill border px-4 py-2 active:opacity-70",
                  selected ? "border-border-strong bg-bg-soft" : "border-border bg-bg",
                )}
              >
                <Text className="text-body-sm text-ink">{opt.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {showStudy ? (
        <TextField
          label="¿QUÉ ESTUDIÁS?"
          placeholder="Ej. Ingeniería, Medicina…"
          value={studyWhat}
          onChangeText={setStudyWhat}
        />
      ) : null}
      {showWork ? (
        <TextField
          label="¿DE QUÉ TRABAJÁS?"
          placeholder="Ej. Diseño, ventas…"
          value={workWhat}
          onChangeText={setWorkWhat}
        />
      ) : null}

      <TextField
        label="¿PARA QUÉ QUERÉS USAR YNARA?"
        placeholder="Ej. organizarme, estudiar mejor…"
        value={purpose}
        onChangeText={setPurpose}
      />
      <TextField
        label="¿QUÉ ES LO QUE MÁS TE INTERESA?"
        placeholder="Ej. música, programación, deporte…"
        value={interests}
        onChangeText={setInterests}
      />
    </StepShell>
  );
}
