"use client";

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";

/**
 * Renderer de markdown **sanitizado** para las respuestas del assistant.
 *
 * Seguridad (plan §2 + AGENTS.md regla #4 / TS strict): `rehype-sanitize`
 * con su schema por defecto (GitHub-like) corre sobre el AST y elimina
 * cualquier HTML crudo / atributos peligrosos. NO se usa
 * `dangerouslySetInnerHTML`. Los links se fuerzan a abrir en pestaña nueva
 * con `rel="noopener noreferrer"`.
 *
 * El subset queda acotado a lo que los modelos emiten: bold, listas, inline
 * code, code blocks, links, párrafos. No hay imágenes ni tablas custom por
 * ahora (el schema default las permitiría, pero el modelo no las produce; si
 * hiciera falta restringir más, se pasa un schema propio acá).
 */
type Props = {
  children: string;
};

export function Markdown({ children }: Props) {
  return (
    <div className="chat-markdown flex flex-col gap-2">
      <ReactMarkdown
        rehypePlugins={[rehypeSanitize]}
        components={{
          a: ({ children: linkChildren, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--color-accent)] underline underline-offset-2"
            >
              {linkChildren}
            </a>
          ),
          code: ({ children: codeChildren, className }) => (
            <code
              className={
                className
                  ? "block overflow-x-auto rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)] p-3 text-body-sm"
                  : "rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)] px-1.5 py-0.5 text-body-sm"
              }
            >
              {codeChildren}
            </code>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
