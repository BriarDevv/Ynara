"use client";

import { useRef } from "react";
import { cta, pricing } from "@/content/ynara";
import { gsap, reducedMotion, registerGsap, useGSAP } from "@/lib/motion";
import { lineReveal } from "@/lib/reveal";
import "./Closing.css";

/**
 * Capítulo Cierre — el clímax. MUNDO CLARO (ivory). Layout distintivo: precio
 * EDITORIAL (no cards en caja, una franja Free/Premium) + un FINALE con el
 * signoff a escala masiva y el CTA principal. Cierra la venta.
 */
export function Closing() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const root = ref.current;
      if (!root || reducedMotion()) return;
      registerGsap();

      const eyebrow = root.querySelector<HTMLElement>(".cl-eyebrow");
      const priceHead = root.querySelector<HTMLElement>(".cl-price-head");
      const plans = gsap.utils.toArray<HTMLElement>(root.querySelectorAll(".cl-plan"));
      const heading = root.querySelector<HTMLElement>(".cl-heading");
      const finaleBits = gsap.utils.toArray<HTMLElement>(root.querySelectorAll(".cl-finale-aux"));

      if (eyebrow) {
        gsap.set(eyebrow, { opacity: 0, y: 14 });
        gsap.to(eyebrow, {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: { trigger: root, start: "clamp(top 80%)" },
        });
      }
      if (priceHead) lineReveal(priceHead, { y: "140%", rot: 2.2, dur: 1.1, stagger: 0.12 });

      for (const plan of plans) {
        const line = plan.querySelector<HTMLElement>(".cl-plan-rule");
        if (line) {
          gsap.set(line, { scaleX: 0, transformOrigin: "left center" });
          gsap.to(line, {
            scaleX: 1,
            duration: 1.1,
            ease: "power3.inOut",
            scrollTrigger: { trigger: plan, start: "clamp(top 88%)" },
          });
        }
        const bits = plan.querySelectorAll<HTMLElement>(
          ".cl-plan-name, .cl-plan-price, .cl-plan-feat",
        );
        gsap.set(bits, { opacity: 0, y: 18 });
        gsap.to(bits, {
          opacity: 1,
          y: 0,
          duration: 0.7,
          ease: "power3.out",
          stagger: 0.05,
          scrollTrigger: { trigger: plan, start: "clamp(top 86%)" },
        });
      }

      if (heading) lineReveal(heading, { y: "150%", rot: 2.5, dur: 1.3, stagger: 0.12 });
      if (finaleBits.length) {
        gsap.set(finaleBits, { opacity: 0, y: 18 });
        gsap.to(finaleBits, {
          opacity: 1,
          y: 0,
          duration: 0.9,
          ease: "power3.out",
          stagger: 0.1,
          scrollTrigger: { trigger: ".cl-finale", start: "clamp(top 78%)" },
        });
      }
    },
    { scope: ref },
  );

  return (
    <section
      ref={ref}
      id="precio"
      className="cl relative"
      aria-label="Precio y cierre"
      data-wipe-tone="ivory"
    >
      <div className="cl-inner">
        {/* PRECIO — franja editorial */}
        <p className="cl-eyebrow">{pricing.eyebrow}</p>
        <h2 className="cl-price-head">{pricing.title}</h2>
        <div className="cl-plans">
          {pricing.plans.map((p) => (
            <div className={`cl-plan${p.featured ? " is-featured" : ""}`} key={p.name}>
              <span className="cl-plan-rule" aria-hidden />
              <div className="cl-plan-row">
                <h3 className="cl-plan-name">{p.name}</h3>
                <p className="cl-plan-price">
                  {p.price}
                  <span className="cl-plan-period"> · {p.period}</span>
                </p>
              </div>
              <ul className="cl-plan-feats">
                {p.features.map((f) => (
                  <li className="cl-plan-feat" key={f}>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="cl-note">{pricing.note}</p>

        {/* FINALE — signoff masivo + CTA */}
        <div className="cl-finale">
          <h2 className="cl-heading">{cta.title}</h2>
          <p className="cl-finale-aux cl-body">{cta.statement}</p>
          <div className="cl-finale-aux cl-cta-row" id="descargar">
            <a className="cl-cta" href={cta.primary.href}>
              {cta.primary.label}
            </a>
            <span className="cl-stores">{cta.stores.join("  ·  ")}</span>
          </div>
        </div>
      </div>
    </section>
  );
}
