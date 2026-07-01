"use client";

import { type ElementType, useRef } from "react";
import { cn } from "@/lib/cn";
import { EASE, gsap, reducedMotion, registerGsap, useGSAP } from "@/lib/motion";

type Play = "scroll" | "intro" | "mount";

type RevealTextProps = {
  text: string;
  as?: ElementType;
  className?: string;
  delay?: number;
  stagger?: number;
  start?: string;
  /** scroll = al entrar en viewport · intro = espera el telón · mount = ya. */
  play?: Play;
  /** Marca palabras envueltas en *asteriscos* con el gradiente de marca. */
  markup?: boolean;
};

/**
 * Título que sube palabra por palabra detrás de una máscara (overflow hidden).
 * Mi reveal de hero más fuerte. Respeta reduced-motion.
 */
export function RevealText({
  text,
  as: Tag = "h2",
  className,
  delay = 0,
  stagger = 0.06,
  start = "top 85%",
  play = "scroll",
  markup = false,
}: RevealTextProps) {
  const ref = useRef<HTMLElement>(null);
  const words = text.split(" ");

  useGSAP(
    () => {
      registerGsap();
      const root = ref.current;
      if (!root) return;
      const inners = root.querySelectorAll<HTMLElement>("[data-word]");
      if (reducedMotion()) {
        gsap.set(inners, { yPercent: 0, opacity: 1 });
        return;
      }

      const vars = {
        yPercent: 118,
        opacity: 0,
        duration: 0.95,
        ease: EASE,
        stagger,
        delay,
      };

      if (play === "scroll") {
        gsap.from(inners, {
          ...vars,
          scrollTrigger: { trigger: root, start, once: true },
        });
        return;
      }

      // intro / mount: tween pausado, se dispara cuando corresponde.
      const tween = gsap.from(inners, { ...vars, paused: true });
      if (play === "mount" || window.__ynaraIntroDone) {
        tween.play();
        return;
      }
      const go = () => tween.play();
      window.addEventListener("ynara:intro-done", go, { once: true });
      return () => window.removeEventListener("ynara:intro-done", go);
    },
    { scope: ref },
  );

  return (
    <Tag ref={ref} className={cn(className)}>
      {words.map((w, i) => {
        const accent = markup && /^\*.*\*$/.test(w);
        const clean = accent ? w.replace(/^\*|\*$/g, "") : w;
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: palabras estáticas
          <span key={i}>
            <span style={{ display: "inline-block", overflow: "hidden", verticalAlign: "top" }}>
              <span
                data-word
                className={accent ? "text-gradient-blue" : undefined}
                style={{ display: "inline-block" }}
              >
                {clean}
              </span>
            </span>
            {i < words.length - 1 ? " " : ""}
          </span>
        );
      })}
    </Tag>
  );
}
