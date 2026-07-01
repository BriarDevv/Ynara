import { useId } from "react";

const BODY_D =
  "M820.99,335.09c-49.27,52.6-62.12,60.65-106.09,109.14-50.19,55.36-66.07,80.85-74.08,94.62-6.88,11.82-23.51,41.74-36.59,81.69-13.87,42.4-18.58,80.28-19.97,111.23-.08,1.88-.16,3.74-.22,5.57-.76,22.58.15,41.17.22,54.77v101.74c0,11.14-9.03,20.16-20.16,20.16h-117.54c-11.14,0-20.17-9.02-20.17-20.16v-197.78c-.54-4.12-1.13-8.35-1.78-12.69-4.88-32.62-9.95-51.11-13.58-62.84-3.98-12.89-14.42-43.59-36.59-81.69-8.01-13.77-23.89-39.26-74.08-94.62-43.96-48.49-56.82-56.54-106.09-109.14-15.74-16.8-29.13-31.13-40.04-43.19-.01-.02-.03-.03-.05-.05-5.07-5.61-9.6-10.72-13.57-15.37-.03-.03-.05-.05-.07-.08-16.3-19.04-23.38-30.26-20.31-35.19.12-.19.25-.37.39-.55,0,0,.13-.17.28-.32,12.69-13.4,73.8,9.52,73.8,9.52,4.39,1.65,65.61,24.95,121.94,62.84,3.75,2.52,7.39,5.05,7.39,5.05,11.75,8.16,32.79,23.44,56.95,44.86.02.01.03.03.05.04,15.91,14.11,33.17,30.86,50.01,49.98.12.12.22.23.31.34.27.3.49.55.67.76.12.14.23.26.31.36.06.08.13.15.2.23.05.05.07.08.07.08.05.05.09.11.14.16,21.5,24.66,42.24,53.19,58.51,84.97h0c5.77,11.28,10.98,22.96,15.46,35.02.32.84.62,1.68.92,2.52.3-.85.61-1.69.93-2.52.25-.66.49-1.32.75-1.98,46.96-123.85,170.08-206.9,189.31-219.87,84.27-56.85,185.98-88.22,196.41-71.49,5.45,8.73-20.97,37.23-74.04,93.88Z";

const HL_D =
  "M584.17,791.52v94.41c-.17.07-.35.12-.52.14-18.27,2.15-17.66-209.61-132.5-324.38-54.45-54.41-87.55-77.11-87.55-77.11,0,0-40.39-27.69-74.3-57.48-1.06-.93-2.1-1.86-2.1-1.86-3.27-2.95-7.68-7.23-23.79-23.07-30.01-29.52-45.29-44.57-59.3-59.02-16.19-16.7-13.25-14.2-24.36-25.44-12.56-12.71-20.38-20.01-26.72-26.4-.01-.02-.03-.03-.05-.05-4.91-4.95-8.93-9.38-13.6-15.37-.03-.03-.05-.05-.07-.08-15.01-19.27-23.39-30.02-20.36-35.19.13-.22.27-.39.39-.55,0,0,3.28-4.21,12.4-3.92,63.97,2.02,131.61,44.77,131.61,44.77,27.03,13.34,46.36,26.22,59.27,35.78,17.03,12.62,57.73,45.29,57.75,45.31,0,0,.01,0,.02.02,0,0,.02.01.03.02,23.97,20.67,44.48,43.53,50.14,49.98.12.12.22.23.31.34.27.3.49.55.67.76.12.14.23.26.31.36.06.08.13.15.2.23.05.05.07.08.07.08.03.03.11.13.14.16,15.92,18.18,47.44,54.75,69.92,109.23.06.14,1.76,4.52,5.16,13.28,14.8,38.1,22.2,57.15,27.76,71.72,19.45,50.96,21.67,60.42,39.79,106.05,3.78,9.52,6.95,17.33,9.05,22.49-.76,22.58.15,41.17.22,54.77Z";

const DIAMOND = {
  x: 422.72,
  y: 141.9,
  w: 169.7,
  h: 168.93,
  rx: 17.08,
  transform: "translate(308.73 -292.6) rotate(45)",
};

type Variant = "gradient" | "ivory" | "blue";

/**
 * Mark de Ynara (guía 2026): figura con brazos + diamante de presencia.
 * `gradient` = mark de marca (diamante violeta + cuerpo azul + highlight).
 * `ivory` / `blue` = monocromo plano para nav / footer.
 */
export function YnaraMark({
  size = 40,
  variant = "gradient",
  className,
  title = "Ynara",
}: {
  size?: number;
  variant?: Variant;
  className?: string;
  title?: string;
}) {
  const uid = useId().replace(/[:]/g, "");
  const flat = variant === "ivory" ? "#f3f0ea" : variant === "blue" ? "#2f5aa6" : null;

  return (
    <svg
      width={size}
      height={size}
      viewBox="117 107 779 807"
      fill="none"
      role="img"
      aria-label={title}
      className={className}
    >
      {variant === "gradient" ? (
        <>
          <defs>
            <linearGradient
              id={`${uid}-p`}
              x1="394.92"
              y1="226.37"
              x2="620.21"
              y2="226.37"
              gradientTransform="translate(-11.4 425.21) rotate(-45)"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset="0" stopColor="#8165a3" />
              <stop offset=".33" stopColor="#7b559b" />
              <stop offset=".98" stopColor="#692e87" />
              <stop offset="1" stopColor="#692d87" />
            </linearGradient>
            <linearGradient
              id={`${uid}-b`}
              x1="119.53"
              y1="575.07"
              x2="895.73"
              y2="575.07"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset=".5" stopColor="#2f5aa6" />
              <stop offset=".85" stopColor="#242552" />
            </linearGradient>
            <linearGradient
              id={`${uid}-h`}
              x1="118.34"
              y1="561.11"
              x2="584.17"
              y2="561.11"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset=".18" stopColor="#2f5aa6" />
              <stop offset=".76" stopColor="#fff" />
              <stop offset=".94" stopColor="#2f5aa6" />
            </linearGradient>
          </defs>
          <rect
            fill={`url(#${uid}-p)`}
            x={DIAMOND.x}
            y={DIAMOND.y}
            width={DIAMOND.w}
            height={DIAMOND.h}
            rx={DIAMOND.rx}
            ry={DIAMOND.rx}
            transform={DIAMOND.transform}
          />
          <path fill={`url(#${uid}-b)`} d={BODY_D} />
          <path fill={`url(#${uid}-h)`} opacity="0.21" d={HL_D} />
        </>
      ) : (
        <>
          <rect
            fill={flat ?? "#f3f0ea"}
            x={DIAMOND.x}
            y={DIAMOND.y}
            width={DIAMOND.w}
            height={DIAMOND.h}
            rx={DIAMOND.rx}
            ry={DIAMOND.rx}
            transform={DIAMOND.transform}
          />
          <path fill={flat ?? "#f3f0ea"} d={BODY_D} />
        </>
      )}
    </svg>
  );
}
