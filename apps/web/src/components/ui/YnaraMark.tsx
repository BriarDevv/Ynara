type Props = {
  size?: number;
  className?: string;
  title?: string;
};

export function YnaraMark({ size = 96, className, title = "Ynara" }: Props) {
  return (
    <svg
      viewBox="0 0 800 700"
      width={size}
      height={size}
      role="img"
      aria-label={title}
      className={className}
    >
      {/*
       * Stops sincronizados con --color-{blue-base,blue-relief,violet}-{from,to}
       * de globals.css. Si cambia un token, actualizar acá también.
       * Los fallbacks hex son por si el var() no resuelve (e.g. Safari viejo
       * con SVG en contextos donde no hereda CSS vars, o uso fuera del DOM).
       */}
      <defs>
        <linearGradient
          id="ynara-y-base"
          x1="240"
          y1="590"
          x2="560"
          y2="160"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--color-blue-base-from, #2F5AA6)" />
          <stop offset="1" stopColor="var(--color-blue-base-to, #1F66DB)" />
        </linearGradient>
        <linearGradient
          id="ynara-y-relief"
          x1="330"
          y1="580"
          x2="470"
          y2="185"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--color-blue-relief-from, #4B7EE6)" stopOpacity="0.88" />
          <stop offset="1" stopColor="var(--color-blue-relief-to, #7BA1F4)" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient
          id="ynara-y-diamond"
          x1="400"
          y1="48"
          x2="400"
          y2="168"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--color-violet-from, #8C63B8)" />
          <stop offset="1" stopColor="var(--color-violet-to, #7C4FA3)" />
        </linearGradient>
      </defs>

      <path
        d="M352 590 C352 590 352 470 352 427 C352 375 324 318 257 212 C241 188 218 173 192 181 C167 188 156 211 168 233 C221 335 269 413 302 485 C320 523 329 557 329 590 L471 590 C471 557 480 523 498 485 C531 413 579 335 632 233 C644 211 633 188 608 181 C582 173 559 188 543 212 C476 318 448 375 448 427 C448 470 448 590 448 590 Z"
        fill="url(#ynara-y-base)"
      />
      <path
        d="M403 590 C403 541 394 498 378 457 C348 385 312 320 255 227 C247 213 238 201 233 192 C252 186 269 194 281 213 C343 311 379 372 399 422 C419 372 455 311 517 213 C529 194 546 186 565 192 C560 201 551 213 543 227 C486 320 450 385 420 457 C404 498 395 541 395 590 Z"
        fill="url(#ynara-y-relief)"
      />
      <path d="M400 48 L464 112 L400 176 L336 112 Z" fill="url(#ynara-y-diamond)" />
    </svg>
  );
}
