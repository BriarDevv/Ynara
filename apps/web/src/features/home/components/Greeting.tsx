"use client";

import { useEffect, useState } from "react";
import { getGreeting } from "@/lib/time";

type Props = {
  displayName: string;
  mood: readonly string[];
  moodFreeText: string;
};

/**
 * Mapeo de los valores de mood (del Step "día") a un adjetivo natural para
 * la línea sutil del saludo. Se mantiene local al home para no acoplarlo al
 * feature de onboarding; si el catálogo de moods crece, actualizar acá.
 */
const MOOD_PHRASES: Record<string, string> = {
  tranquilo: "tranquilo",
  ocupado: "ocupado",
  estresado: "movido",
  confuso: "medio confuso",
  creativo: "creativo",
  cansado: "cansado",
};

function moodLine(mood: readonly string[], freeText: string): string | null {
  if (freeText.trim()) return `Anoté lo que me contaste: «${freeText.trim()}».`;
  const phrases = mood.map((m) => MOOD_PHRASES[m]).filter(Boolean);
  if (phrases.length === 0) return null;
  return `Anoté que tu día viene ${phrases.join(" y ")}.`;
}

/**
 * Saludo del home: "Buenas tardes, Mateo" según la hora + el displayName,
 * con una segunda línea sutil si el usuario declaró su mood (plan §5.2).
 *
 * El saludo se calcula en el cliente tras montar para evitar mismatch de
 * hidratación (el server no conoce la hora local del usuario).
 */
export function Greeting({ displayName, mood, moodFreeText }: Props) {
  const [greeting, setGreeting] = useState<string | null>(null);

  useEffect(() => {
    setGreeting(getGreeting());
  }, []);

  const line = moodLine(mood, moodFreeText);
  const name = displayName.trim();

  return (
    <header className="flex flex-col gap-2">
      {/* Saludo como pieza editorial: big type (§4). */}
      <h1 className="text-display text-balance">
        {greeting ? `${greeting}${name ? `, ${name}` : ""}` : name || "Hola"}
      </h1>
      {line ? <p className="text-body text-[var(--color-ink-soft)]">{line}</p> : null}
    </header>
  );
}
