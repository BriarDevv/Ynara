"use client";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

/**
 * Confirmación de cierre de sesión (M3): aviso suave antes de salir de la
 * cuenta. El usuario tiene que volver a entrar para seguir.
 */
export function LogoutDialog({ open, onClose, onConfirm }: Props) {
  return (
    <Sheet open={open} onClose={onClose} title="Cerrar sesión">
      <div className="flex flex-col gap-5">
        <p className="text-body text-[var(--color-ink)]">
          Vas a salir de tu cuenta. Vas a tener que volver a entrar para seguir.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row-reverse">
          <Button variant="primary" fullWidth onClick={onConfirm} aria-label="Cerrar sesión">
            Cerrar sesión
          </Button>
          <Button variant="ghost" fullWidth onClick={onClose}>
            Cancelar
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
