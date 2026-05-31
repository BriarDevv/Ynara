import { ICON_SHAPES } from "./registry";
import type { IconProps, IconShape } from "./types";

const VIEWBOX = 44;

function renderShape(shape: IconShape, key: number) {
  switch (shape.type) {
    case "circle":
      return <circle key={key} cx={shape.cx} cy={shape.cy} r={shape.r} />;
    case "rect": {
      const transform =
        shape.rotate !== undefined
          ? `rotate(${shape.rotate} ${shape.x + shape.w / 2} ${shape.y + shape.h / 2})`
          : undefined;
      return (
        <rect
          key={key}
          x={shape.x}
          y={shape.y}
          width={shape.w}
          height={shape.h}
          rx={shape.rx}
          transform={transform}
        />
      );
    }
    case "path":
      return <path key={key} d={shape.d} />;
    default: {
      // Exhaustividad: si se agrega un IconShape nuevo, esto es error de compilación.
      const _exhaustive: never = shape;
      return _exhaustive;
    }
  }
}

/**
 * Ícono del set propio de Ynara (DESIGN.md §9). Renderer web: lee la
 * geometría de `ICON_SHAPES` y la traza como `<svg>`. El trazo es uniforme
 * a cualquier `size` (escala con el viewBox). Decorativo por defecto;
 * accesible si se pasa `title`.
 */
export function Icon({
  name,
  size = 24,
  strokeWidth = 2.2,
  color = "currentColor",
  className,
  title,
}: IconProps) {
  const decorative = title === undefined;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-label={decorative ? undefined : title}
      focusable={false}
    >
      {title !== undefined ? <title>{title}</title> : null}
      {ICON_SHAPES[name].map(renderShape)}
    </svg>
  );
}
