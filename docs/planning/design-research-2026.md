# Reporte de dirección de diseño 2026 — Ynara

> Síntesis de 5 vectores de investigación (tipografía, color, motion, chat UI, anti-slop) más verificación adversarial de las afirmaciones clave. Objetivo: que valides la dirección **antes** de reescribir `DESIGN.md`.
> Premisa fija: **refinar, no reinventar**. Se mantiene la identidad actual (ink `#242C3F`, gradientes azul/violeta/jade/ámbar, Space Grotesk + DM Sans) y se sube el nivel de craft.
> Convención: marco cada recomendación como **[evidencia]** (respaldado por fuentes) o **[criterio]** (decisión de diseño mía, opinionada).

---

## 1. TL;DR — la dirección en 7 bullets

- **No tocamos las fuentes, afinamos la escala.** Space Grotesk + DM Sans ya tienen carácter; el ROI está en type scale fluida con `clamp()`, tracking negativo en display y measure acotado. **[evidencia]** El "tell" premium está en line-height/tracking por rol, no en qué fuente elegís [3].
- **Calentamos los neutros y tintamos el dark.** Nada de `#FFF` ni `#000` puros: off-white cálido para light, near-black tintado del azul de marca para dark. Esto solo ya saca a Ynara del look genérico [8][9].
- **Gradientes con grano, y solo de ambiente.** Overlay de ruido 3-6% sobre los gradientes existentes para matar el banding; los gradientes pasan a fondo/hero, nunca en UI funcional. Es el cambio de mayor leverage para pasar de "generado" a "crafteado" [7][8] — *con un matiz, ver Riesgos*.
- **Motion = springs perceptuales + microinteracciones, no decoración.** Sistema de tokens de motion (duraciones 100-300ms, springs nombrados con `visualDuration`+`bounce`), feedback en hover/press/focus, View Transitions nativas. **[evidencia fuerte]** El modelo duration+bounce está respaldado por Apple y Figma, no solo por la doc citada [12][13].
- **El chat se vuelve "documento", no "mensajería".** Eliminamos la burbuja del asistente (respuesta a ancho de columna acotada con prosa real), el usuario conserva contenedor liviano, streaming token-a-token con cursor, auto-scroll que respeta el scroll manual [16].
- **Matamos los "AI tells" primero.** Fuera gradiente violeta-azul default + glassmorphism porque sí, fuera emojis como íconos (un solo set: Lucide o Phosphor), fuera centrado-en-todo, fuera copy buzzword [20][21].
- **Todo vive en design tokens.** Spacing scale fija, 8-10 shades por color en HSL, elevación por luz (no shadow) en dark, un único utility de ruido. Si no está tokenizado, derrapa de vuelta al default [22][8].

---

## 2. Vectores

### 2.1 Tipografía expresiva

**Qué dice la evidencia.** La tipografía premium 2025-2026 se define por *cómo se afina*, no por qué fuente: variable fonts con ejes `wght`/`opsz`/`GRAD` [1], type scale fluida con `clamp()` (rem + vw, nunca vw puro, para no romper zoom) [2], y contraste expresivo entre un display con tracking negativo y un body neutral legible [3][5]. El rubro divide aguas: SaaS usa grotescas neutras, wellness suma serifs humanistas para calidez [4]. El "big type" con tracking negativo es la tendencia expresiva dominante [5].

**Recomendaciones para Ynara:**

1. **[evidencia]** Mantener Space Grotesk (display) + DM Sans (body), pero usar el **archivo variable** y exponer el eje `wght`: 400 body, 500-600 UI/emphasis, 700 display. Jerarquía con peso + contraste, no solo tamaño [3].
2. **[criterio, anclado en evidencia]** Type scale fluida con dos anclas (360px / 1240px):
   ```css
   --step--1: clamp(0.875rem, 0.84rem + 0.18vw, 0.95rem);
   --step-0:  clamp(1rem,    0.95rem + 0.25vw, 1.125rem);   /* body */
   --step-1:  clamp(1.25rem, 1.15rem + 0.5vw,  1.5rem);
   --step-2:  clamp(1.6rem,  1.4rem + 1vw,     2.25rem);
   --step-3:  clamp(2.1rem,  1.7rem + 2vw,     3.25rem);
   --step-4:  clamp(2.6rem,  1.9rem + 3.5vw,   4.5rem);     /* display/hero */
   ```
   Ratio ~1.2 en mobile, ~1.25-1.33 en desktop. Siempre `rem + vw` [2].
3. **[evidencia]** Tracking y line-height por rol:
   - Display (Space Grotesk): `letter-spacing: -0.02em a -0.03em`, `line-height: 1.05-1.15`.
   - Body (DM Sans): `line-height: 1.5-1.6`, `tracking 0`.
   - Labels uppercase: `letter-spacing: +0.06em` [3].
4. **[criterio]** Sumar **un** acento serif humanista variable y **gratis** (Source Serif 4 variable es la apuesta segura; Reckless/Canela son de pago) SOLO para momentos empáticos (saludo del asistente, quotes de bienestar). Máximo 3 familias.
5. **[evidencia]** Activar `font-variant-numeric: tabular-nums` para timestamps/datos del chat, comillas curvas y em-dash reales en copy. Measure del asistente acotado a **60-70ch** [3].

---

### 2.2 Color cálido y gradientes con carácter

**Qué dice la evidencia.** El color de producto 2026 se aleja del frío "default Tailwind": superficies cálidas y atmosféricas. Señales dominantes: gradientes mesh/multi-stop con overlay de grano para matar banding [7]; nada de blanco/negro puro (off-whites cálidos para light, near-blacks tintados para dark) [9]; en dark, superficies neutras tintadas al hue de marca con elevación expresada por **luz** (más alto = más claro), no por shadow [9]; y contraste evaluado con APCA, más preciso que WCAG 2.x para dark UI [10]. La calidez se logra con un shift de temperatura sutil en toda la rampa de neutros, no saturando todo [11].

**Recomendaciones para Ynara:**

1. **[evidencia]** Mantener ink `#242C3F` como ancla, pero calentar neutros: reemplazar todo blanco puro por off-white cálido (~`#F7F5F1`), nunca `#000`. En dark, tintar los near-black hacia el azul de marca (2-6% de saturación de `#242C3F`) para que el dark "se sienta Ynara" [9].
2. **[evidencia, con matiz]** Inyectar overlay de ruido monocromo 3-6% sobre los gradientes existentes (SVG `feTurbulence` o PNG tileado, costo casi nulo) para matar el banding [7]. *Ojo: ver Riesgos — el grano es una técnica válida, no "el marcador de calidad", y está cerca de cliché. Aplicar con sobriedad.*
3. **[evidencia]** Degradar gradientes a rol **ambiente/hero**: grandes, desaturados, lentos. UI funcional (botones, texto, bordes, estados) sobre colores sólidos accesibles [8].
4. **[DECISIÓN — validada por el usuario]** La calidez sale **solo de la superficie marfil cálida + la textura de grano de marca**, sin sumar un acento cálido nuevo. La paleta se mantiene **100% fiel al universo de marca (azul → violeta)**; no se introduce ámbar/oro como acento global. Más sobrio y coherente con la guía. (El ámbar/jade siguen siendo solo tints por-modo donde ya existen, no acento de sistema — ver §6.6.5).
5. **[evidencia]** Elevación dark por luz: rampa `base / +1 / +2` donde cada capa superior es unos % más clara (overlay blanco semitransparente sobre el dark tintado) [9].
6. **[evidencia]** Adoptar targets **APCA** como guía de diseño en dark (Lc ~75+ body, ~60 secundario/large) y validar igual contra WCAG 2.1 AA por compliance [10].

---

### 2.3 Motion y microinteracciones

**Qué dice la evidencia.** Motion premium = física de springs (no easing fijo) con valores snappy y cortos; microinteracciones de feedback en cada estado; shared-element transitions vía View Transitions API; stagger sutil [12][14][15]. Regla de oro: animar solo `transform`/`opacity` (GPU), 150-300ms para UI utilitaria, bounce bajo (0-0.2) [12][14]. El modelo `visualDuration` + `bounce` está **verificado y respaldado** por la fuente originaria (Apple WWDC 2023) y Figma, no solo por Motion.dev [12]. Lo amateur es lo opuesto: >500ms, bouncy de más, loops decorativos [12][14].

**Recomendaciones para Ynara:**

1. **[criterio, anclado en evidencia]** Tokens de motion como única fuente de verdad:
   ```css
   --dur-instant: 100ms; --dur-fast: 150ms; --dur-base: 200ms; --dur-slow: 300ms;
   /* springs (config Motion): */
   /* spring-snappy: visualDuration 0.2, bounce 0   */
   /* spring-soft:   visualDuration 0.35, bounce 0.15 */
   ```
   [12]
2. **[evidencia]** Microinteracciones de feedback primero (alto ROI): hover `scale(1.02)` + elevación en cards/botones, press `scale(0.97-0.98)`, `focus-visible` con ring animado para a11y. Todo `transform`/`opacity`, 150-200ms [14].
3. **[evidencia]** Skeleton loaders (shimmer sutil) en lugar de spinners en vistas content-heavy (conversación, listas de memoria) [14].
4. **[evidencia]** View Transitions API nativa para cambios de ruta y shared-element, con progressive enhancement (`if (document.startViewTransition)`) y fallback sin animación. `view-transition-name` únicos y pocos [13].
5. **[evidencia]** Stagger sutil en listas (delay 30-50ms/item, máx ~5-6 items) con fade + `translateY(8-12px)`. Respetar `prefers-reduced-motion` globalmente (guard CSS + `useReducedMotion` en Motion) [13][14].

---

### 2.4 Chat UI / asistente

**Qué dice la evidencia.** El estado del arte se movió de "mensajería" a "documento": respuesta del asistente sin burbuja pesada, a ancho de columna acotada con markdown completo, mientras el turno del usuario conserva contenedor liviano [16]. Premium = jerarquía tipográfica, streaming token-a-token con cursor sutil, auto-scroll inteligente que respeta el scroll manual, indicadores diferenciados (pensando/buscando/generando), botón stop prominente, citaciones/tool-calls como bloques estructurados [16][17][18]. Anti-patrones: burbujas pesadas en ambos roles, emojis como controles, texto plano sin markdown, placeholder genérico, spinners sin contexto [16].

**Recomendaciones para Ynara:**

1. **[evidencia + criterio]** Eliminar la burbuja del asistente: respuesta sin globo, a ancho de columna **max ~680-720px centrada**, prosa real (`line-height ~1.5-1.6`, 15-16px). El turno del usuario, contenedor liviano alineado a la derecha [16]. *(El ancho exacto es criterio mío; las fuentes coinciden en "columna acotada" sin dar px.)*
2. **[evidencia]** Reemplazar TODAS las flechas/emojis por un set vectorial consistente (Lucide o Phosphor, uno solo). El control de envío se transforma en **stop prominente** durante el streaming, no en menú [16][18][20].
3. **[evidencia]** Composer como "editor vivo": textarea autosize multi-línea con tope (~6-8 líneas y luego scroll), Enter envía / Shift+Enter newline, estados draft/sending/streaming/disabled, barra de acciones (adjuntar izquierda, send/stop derecha) [17].
4. **[evidencia]** Auto-scroll inteligente: seguir el stream solo si el usuario está cerca del fondo; si scrollea arriba, pausar y mostrar botón flotante "ir al final" (chevron). **Corregir el auto-scroll de W2 para que no secuestre la lectura** [16].
5. **[evidencia]** Streaming robusto: cursor sutil (~2px parpadeando ~500ms) que desaparece al terminar; **bufferizar markdown incompleto** y diferir bloques de código hasta cerrar el fence (que un `**` o ``` a medias no rompa el layout). Evitar re-layout por token [17][18].
6. **[evidencia]** Indicadores diferenciados con voz de Ynara (pensando/buscando/generando) + skeleton antes del primer token. Tool-calls `memory.*` como acordeones colapsables ("Usando memoria…"), no texto crudo [18]. Empty state como onboarding: welcome + 3-4 chips de prompt accionables, nunca placeholder genérico [18]. Accesibilidad: `aria-live="polite"` `aria-atomic="false"` debounced, orden de tab predecible, no robar foco al terminar [17].

---

### 2.5 Anti-slop (que no se vea generado por IA)

**Qué dice la evidencia.** El look "IA/maqueta de trainee" ya es un cliché reconocible: gradientes violeta-azul, glassmorphism, Inter default, emojis como íconos, todo centrado, grids de tres columnas idénticas, spacing uniforme, shadows genéricas y copy buzzword [20][21]. El fix no es más decoración sino craft: sistema de tokens acotado (spacing scale, 8-10 shades por color en HSL, shadows en capas con una sola fuente de luz) [22], jerarquía por peso/contraste y no por tamaño [22], un solo set de íconos [20], layouts asimétricos basados en grid [21], y microcopy específico con voz [21].

**Recomendaciones para Ynara:**

1. **[evidencia, con matiz]** Matar los "AI tells" primero (win visible más rápido): fuera gradiente violeta-azul default + glassmorphism sin propósito, fuera centrado-en-todo, fuera emoji-como-ícono [20][21]. *Matiz: "el gradiente violeta-azul es LA señal más fuerte" está overstated (ver Riesgos); tratalo como una de varias señales comunes, no como el único enemigo.*
2. **[evidencia]** Lockear tokens en CSS custom properties **antes** de tocar pantallas:
   - Spacing scale fija: `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 / 128`. Nada de px arbitrarios.
   - 8-10 greys + 8-10 shades por acento en **HSL**.
   - Elevación 4-5 pasos con **una** fuente de luz top-down (en dark, elevación por luz, no shadow) [22].
3. **[evidencia]** Jerarquía con peso + contraste, no tamaño: dos pesos (400-500 body, 600-700 emphasis); de-enfatizar bajando contraste, no agrisando; spacing **no uniforme** (más gap entre grupos que dentro) [22].
4. **[criterio]** Romper el centrado simétrico + grid de tres tarjetas iguales por un layout intencional levemente asimétrico; darle a la pantalla de conversación un foco claro, no bloques balanceados pero planos [21].
5. **[evidencia]** Reescribir copy genérico a la voz de Ynara (empty states, labels, errores, loading). Craft barato y de alta señal que los defaults de IA nunca producen [21].

---

## 3. Lo que delata el look amateur en Ynara HOY y cómo arreglarlo

Checklist accionable (priorizado por leverage / esfuerzo):

- [ ] **Auto-scroll que secuestra la lectura (W2).** → Auto-scroll inteligente: seguir solo si está cerca del fondo + botón "ir al final". *(Alto leverage, ya identificado en el código.)*
- [ ] **Burbujas en ambos roles.** → Asistente sin globo a ancho de columna; usuario con contenedor liviano.
- [ ] **Emojis/flechas como controles.** → Un solo set de íconos (Lucide o Phosphor). Send → Stop durante streaming.
- [ ] **Blanco/negro puros.** → Off-white cálido `#F7F5F1` + near-black tintado del azul de marca.
- [ ] **Gradientes con banding y/o en UI funcional.** → Overlay de ruido 3-6% + gradientes solo en fondo/hero.
- [ ] **Spacing y shadows ad-hoc.** → Spacing scale fija + elevación tokenizada con una sola fuente de luz.
- [ ] **Jerarquía solo por tamaño.** → Peso + contraste; spacing no uniforme.
- [ ] **Todo centrado / simétrico.** → Grid intencional levemente asimétrico con foco claro.
- [ ] **Sin microinteracciones (se ve estático).** → hover/press/focus con `transform`/`opacity` 150-200ms.
- [ ] **Spinners genéricos.** → Skeletons + indicadores diferenciados (pensando/buscando/generando).
- [ ] **Markdown frágil en streaming.** → Bufferizar markdown incompleto, diferir code blocks al cierre del fence.
- [ ] **Placeholder genérico ("Escribí algo…").** → Welcome + 3-4 chips de prompt accionables con voz de Ynara.
- [ ] **Copy buzzword.** → Microcopy específico y humano por estado.
- [ ] **Sin `prefers-reduced-motion`.** → Guard global (CSS + `useReducedMotion`), incluyendo pseudo-elementos de view-transition.

---

## 4. Riesgos / afirmaciones débiles (verificación adversarial)

Cosas a **no** escribir como dogma en `DESIGN.md`:

1. **"Variable fonts = mejor performance, son el estándar 2026" → OVERSTATED.** Los mecanismos (`wght`/`opsz`/`GRAD`, uso en Roboto Flex y SF Pro) son correctos. **Pero** un archivo variable es 2-5x más pesado que una instancia estática; solo gana en bytes con **2-4+ pesos** usados. Si Ynara usa 1-2 pesos, el estático es más liviano. Y "estándar" es lenguaje de tendencia, no dato de adopción medido (la fuente es un vendor de fuentes). **Implicancia:** elegir variable según cuántos pesos usemos realmente, no por fe. Como recomendamos 3 pesos por familia (400/500-600/700), variable probablemente conviene — pero validar con el bundle real.

2. **"El grano es EL marcador de calidad de los gradientes" → OVERSTATED.** El mecanismo (ruido = dithering que mata banding de 8-bit) es sólido y verificado. **Pero** "el marcador de calidad" es opinión vendida como hecho; el grano es UNA técnica, hoy cerca del **cliché** ("la tendencia que no muere"), y su uso real es más decorativo/filmic que anti-banding. El rango "3-8%" no es un estándar canónico, solo "sutil". La fuente citada (`designsystems.com`) no se pudo verificar. **Implicancia:** usar grano con sobriedad y propósito (matar banding en superficies grandes), no como sello obligatorio de "premium".

3. **"El gradiente violeta-azul es LA señal más fuerte de IA" → OVERSTATED.** Es **una** señal común y citada, sí. **Pero** "la más fuerte/única" es jerarquización sin evidencia empírica (blogs de opinión que se citan entre sí). Hay tells igual de fuertes: Inter en todo, copy hueco, hero centrado con badge-pill, íconos default, emojis como bullets. Además el gradiente violeta-azul fue tendencia legítima pre-IA (Stripe) y el glassmorphism revivió con "Liquid Glass" de Apple 2025. **Implicancia:** no obsesionarse con un solo enemigo; atacar el conjunto de tells.

4. **"Asistente full-width sin burbuja = patrón premium 2026" → SUPPORTED, con descuento de rótulo.** El hecho observable (ChatGPT/Claude/Gemini renderizan el asistente a ancho de columna sin globo, usuario con contenedor) es **real y verificable**. **Pero** el término "AI Assistant Cards" es acuñación de un blog de marketing, no terminología de industria, y "tendencia premium 2026" es posicionamiento: es el patrón **actual dominante** (coexiste con burbujas en widgets/móvil), no una novedad emergente. **Implicancia:** adoptarlo con confianza por sustancia, sin citar el rótulo de marketing.

**Lo que SÍ está sólido (verificado supported):**
- **Springs con modelo `visualDuration` + `bounce`** como enfoque moderno de motion: respaldado por Apple WWDC 2023 (fuente originaria) y Figma, no solo por la doc citada. Datos numéricos (bounce 0.25 / duration 0.8s default; física cruda stiffness 100 / damping 10 / mass 1) verificados [12].
- **Chat "documento" (asistente full-width sin globo)** como hecho observable (ver punto 4).

---

## 5. Fuentes

1. Google Fonts Knowledge — Working with variable fonts: https://fonts.google.com/knowledge/using_type_tools/working_with_variable_fonts
2. Utopia — Designing with fluid type scales: https://utopia.fyi/blog/designing-with-fluid-type-scales/
3. Practical Typography (Butterick): https://practicaltypography.com/
4. Typewolf — Recommendations: https://www.typewolf.com/recommendations
5. Smashing Magazine — Modern fluid typography with CSS clamp(): https://www.smashingmagazine.com/2024/11/modern-fluid-typography-css-clamp/
6. *(reservado)*
7. Design Systems — The power of gradients: https://www.designsystems.com/the-power-of-gradients/
8. Stripe — Designing the Stripe gradient: https://stripe.com/blog/gradient
9. Material Design 2 — Dark theme: https://m2.material.io/design/color/dark-theme.html
10. APCA — Why APCA: https://git.apcacontrast.com/documentation/WhyAPCA
11. Canva — Color trends: https://www.canva.com/learn/color-trends/
12. Motion.dev — Spring: https://motion.dev/docs/spring
13. Chrome — View Transitions (same-document): https://developer.chrome.com/docs/web-platform/view-transitions/same-document
14. Smashing Magazine — Microinteractions / premium UX: https://www.smashingmagazine.com/2025/microinteractions-premium-ux/
15. Josh W. Comeau — A friendly introduction to spring physics: https://www.joshwcomeau.com/animation/a-friendly-introduction-to-spring-physics/
16. MultitaskAI — Chat UI design: https://multitaskai.com/blog/chat-ui-design/
17. TheFrontKit — AI chat UI best practices: https://thefrontkit.com/blogs/ai-chat-ui-best-practices
18. AI UX Design Guide — Conversational UI patterns: https://www.aiuxdesign.guide/patterns/conversational-ui
19. UX Design CC — The AI design look and how to avoid it: https://uxdesign.cc/the-ai-design-look-and-how-to-avoid-it
20. Carlos Marcial (Medium) — That AI look in web design and how to avoid it: https://medium.com/@carlosmarcialt/that-ai-look-in-web-design-and-how-to-avoid-it-5ae5f2a51f64
21. Jane Tracy (Medium) — Why most AI-generated UIs look the same: https://medium.com/@janetracy2728/why-most-ai-generated-uis-look-the-same-and-how-to-stand-out-fb88f7e22ad3
22. Refactoring UI (summary): https://github.com/vasanthk/refactoring-ui-summary
23. Josh W. Comeau — Banding in gradients (referido en verificación): https://www.joshwcomeau.com/css/backdrop-filter/

---

## 6. Universo de marca Ynara — el ancla que faltaba

> Fuente: `Ynara-Universo-de-Marca.html` (Guía de identidad visual · Ynara 2026, secciones 01-10). Esto **no es tendencia externa, es la marca propia** — y resulta que valida y ancla casi todo el research. Cuando la marca y la tendencia 2026 coinciden, eso deja de ser "criterio" y pasa a ser dirección.

### 6.1 El concepto rector (y por qué resuelve el problema de raíz)

> **"Tecnología que se siente como pensar."** Ynara no es una IA ruidosa: es una **compañía cognitiva diaria**. Su universo visual es **editorial y sereno — lo opuesto al cliché tecnológico.**

Esa última frase **es** el norte anti-slop. El problema "se ve generado por IA / maqueta de trainee" se resuelve ejecutando lo que la marca ya declara: editorial, sereno, anti-cliché. Tres ideas gobiernan el sistema:

| Idea | Forma | Significado |
|---|---|---|
| **Memoria** | Nodos y puntos de luz | Cada idea/recuerdo capturado. La unidad mínima. |
| **Conexión** | Vínculos e hilos | El tejido que une un pensamiento con el siguiente. |
| **Presencia** | El diamante | Foco y claridad en la profundidad. El acento que ordena. |

### 6.2 Sistema de elementos gráficos — esto REEMPLAZA al gradiente genérico

La marca tiene un lenguaje gráfico **propio y ownable** (sección 03-07). Esto es la respuesta concreta a "gradientes default que se ven generados por IA":

- **Elementos base:** Nodo (idea capturada), Vínculo (asociación), **Bifurcación (la forma de la Y)**, Diamante (acento del logo).
- **Patrón "Red de memoria"** (04): módulo base **320px** que se repite sin costura; nodos enlazados en red orgánica, diamantes como acentos rítmicos. Variaciones de densidad **dispersa / media / densa**. Patrón base = **azul sobre marfil**.
- **Trama "Continuidad"** (05): líneas de flujo paralelo (variación abierta / densa) que traducen la continuidad del pensamiento.
- **Texturas** (06): **Grano** (calidez y materia física), **Campo de nodos** (densidad de ideas), **Profundidad** (atmósfera y niebla nocturna). Regla de oro de marca: *"las texturas se construyen con la geometría del sistema — nunca con fotografía."*
- **Territorio** (07): versión **clara** (superficie base marfil) + versión **nocturna** → el dark mode co-protagonista ya está en la marca, no lo inventamos nosotros.

**Implicancia fuerte:** los fondos de hero, empty states, loading, dividers y secciones ambientales se construyen con **la red de nodos/vínculos/diamantes**, NO con gradientes violeta-azul genéricos. Es el cambio de mayor leverage de todo el rebuild y elimina el AI-tell #1 sin sacrificar profundidad.

### 6.3 Iconografía propia (corrige mi recomendación de Lucide/Phosphor)

La sección 08 define un **set de íconos propio** con el ADN de los elementos: **trazo uniforme + el diamante como acento**. Íconos definidos: Idea, Conexión, Memoria, Nota, Buscar, Diálogo, Recordatorio, Adaptación, Foco, Red.

→ **Revisión del research:** en vez de adoptar Lucide/Phosphor genérico, Ynara debe **implementar/extender su propio set** (trazo uniforme + diamante). Un set custom es uno de los marcadores más fuertes de "producto crafteado vs generado por IA". Lucide queda como *fallback* solo para íconos utilitarios que el set propio no cubra todavía, manteniendo el mismo grosor de trazo.

### 6.4 Slide 09 — Aplicación / "Gran formato" (lo que al usuario le gustó)

El territorio aplicado a piezas de comunicación: **posters editoriales de tipografía grande** con la voz de la marca.

| Pieza | Copy | Versión |
|---|---|---|
| Poster nocturno | **"Orden que te acompaña."** / "Tu compañía cognitiva diaria" | Nocturna |
| Poster claro | **"Pensar mejor, recordar siempre."** / "Una inteligencia que te recuerda" | Clara |
| Poster tipográfico | **"Foco. Memoria. Presencia."** | Tipográfico |

→ **Dirección para hero / onboarding / empty states:** composiciones editoriales de **big type** con el sistema gráfico (red de nodos) como capa ambiental detrás, y **copy con voz de marca** (no buzzwords). Esto es exactamente lo opuesto al "hero centrado con badge-pill" del look IA. El empty state del chat y el onboarding deben sentirse como estas piezas: editoriales, serenos, con una frase que importa.

### 6.5 Cómo se fusiona con el research 2026 (recomendaciones revisadas)

- **Tipografía** → los posters confirman **big type editorial expresivo**. La type scale fluida (§2.1) se ancla a esa sensación de poster. El "carácter" no viene de sumar fuentes raras sino de la **composición editorial** (jerarquía dramática, espacio, una frase grande).
- **Color / gradientes** → **degradar gradientes aún más**: el rol ambiental lo ocupa el **sistema de nodos/vínculos/diamantes + grano**, no un mesh gradient. "Azul sobre marfil" confirma que la superficie base es **marfil cálido** (valida "calentar neutros / nunca blanco puro" — ahora es mandato de marca). El grano deja de ser "cliché 2026" y pasa a ser **textura de marca con propósito** ("calidez y materia física").
- **Motion** → el movimiento puede **expresar el concepto**: nodos que se encienden (memoria), vínculos que se dibujan (conexión), el diamante como acento de foco (presencia). Esto le da **significado** al motion en vez de decoración — un nodo pulsa al guardar memoria, los hilos se trazan al cargar, el diamante marca el estado activo. Sigue respetando springs cortos + `prefers-reduced-motion` (§2.3).
- **Chat UI** → la dirección "editorial / documento" (§2.4) **es la marca** ("editorial y sereno"). El **diamante** puede ser el indicador de "pensando/foco" del asistente; el set de íconos propio reemplaza las flechas emoji; la respuesta del asistente como prosa editorial a ancho de columna.
- **Anti-slop** → el norte ya está escrito por la marca: **"lo opuesto al cliché tecnológico."** El checklist de §3 se ejecuta contra ese estándar.

### 6.6 Tokens reales de la presentación (extraídos literalmente del HTML)

> **Corrección honesta:** un borrador previo de esta sección listaba fuentes/colores que NO están en la presentación (Fraunces, Manrope, `#0B1020`, etc.). Eran un error mío — los escribí antes de tener la extracción real. Estos son los valores **verdaderos**, sacados del `<style>` y los SVG del archivo.

**Tipografía — es la MISMA que ya tenemos (no hay fuente nueva):**

| Rol | Familia | Pesos | Fallback |
|---|---|---|---|
| Display | **Space Grotesk** | 400/500/600/700 | Inter, system-ui, sans-serif |
| Body / UI | **DM Sans** | 400/500/600/700 | Inter, system-ui, sans-serif |

> Carga real: `Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700`.
> ⇒ El "carácter editorial" de los posters (slide 09) sale de la **composición** (big type Space Grotesk, jerarquía dramática, espacio), NO de sumar un serif. Esto **revisa el §2.1**: la idea de meter un serif humanista (Source Serif 4) es *criterio mío*, no de la marca; la marca se banca el carácter con las dos sans actuales bien usadas. Si querés serif, es una decisión a abrir, no algo que la presentación ya tenga.

**Paleta literal (CSS vars + colores de los SVG):**

| Token / color | Valor | Rol |
|---|---|---|
| `--ivory` | `#F3F0EA` (y `#FAF9F5`) | **Superficie clara "marfil" cálida** |
| `--night` | `#242C3F` | **Superficie nocturna / dark** (= el ink actual) |
| Tinta principal | `#242C3F` | Texto sobre claro |
| Tinta secundaria | `#5A6276` | Texto atenuado |
| `--blue` | `#2F5AA6` (+ `#305BA6`) | Azul base de marca |
| `--indigo` | `#434A82` | Azul profundo (transición a violeta) |
| `--violac` | `#5C6FB3` | Azul-violáceo / periwinkle medio |
| Periwinkle | `#8B9AD0` | Acento claro de la red de memoria |
| `--violet` | `#8165A3` | Violeta (memoria) |
| Púrpura | `#692D87` / `#7B559B` | Violeta profundo (acentos) |
| Neutros | `#8A8A8A`, `#CFCFCF` | Grises de apoyo |

> Los gradientes de la presentación están como **`<linearGradient>` en SVG** (`g-blue`, `g-purple`, `g-hl`), no como CSS — coherente con que el sistema gráfico es **geométrico/vectorial** (red de nodos, no mesh-gradient CSS). Sombra observada: `0 6px 30px rgba(0,0,0,.18)`. El contenedor-logo usa radio ~17% (`rx 175` sobre 1010).

**Lo que esto cambia respecto al `DESIGN.md` actual (discrepancias reales):**

1. **Fuentes:** **sin cambios** — Space Grotesk + DM Sans en ambos. (Mi "hallazgo" anterior de Fraunces/Manrope era falso.)
2. **Superficie clara:** presentación usa **marfil `#F3F0EA`/`#FAF9F5`** vs `DESIGN.md` `--color-bg: #FFFFFF`. → **Confirma con valor exacto el "calentar neutros / nunca blanco puro".**
3. **Dark mode:** la versión nocturna usa **`#242C3F` (night)** como fondo pleno; `DESIGN.md` todavía no define dark. → Punto de partida del dark co-protagonista (y ojo: el dark de marca es el azul-tinta de siempre, no un negro nuevo).
4. **Familia violeta/memoria:** la presentación tiene una **rampa violeta más rica** (indigo `#434A82` → violac `#5C6FB3` → periwinkle `#8B9AD0` → violet `#8165A3` → púrpura `#692D87`) que el único `--gradient-violet` del `DESIGN.md`. → La "memoria" amerita una escala propia, no un solo stop.
5. **Acento cálido — RESUELTO:** la presentación NO trae oro/ámbar; su paleta es azul→violeta + marfil. **Decisión validada (usuario): la calidez viene solo del marfil + grano, sin acento cálido nuevo; paleta fiel azul/violeta.** El ámbar/jade quedan acotados a tints por-modo donde ya existen en `DESIGN.md` (Vida/Bienestar), no se promueven a acento de sistema.

---

*Generado por workflow `research-gap-vectors` (11 agentes, ~400k tokens, verificación adversarial 3-perspectiva). Combina con los hallazgos verificados del pass 1: glassmorphism con disciplina, dark mode APCA + "nunca negro puro", arquitectura de tokens semánticos cross-theme/cross-platform (DTCG 2025.10 + Tailwind v4 `@theme` + NativeWind `vars()`). **§6 añadido tras incorporar `Ynara-Universo-de-Marca.html` (universo de marca propio).***
