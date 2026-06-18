"use client";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";

type Props = {
  open: boolean;
  /** Cuenta de invitado (efímera): el logout borra todo sin recuperación. */
  isEphemeral: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

/**
 * Confirmación de cierre de sesión (M3). Para cuentas efímeras ("invitado") el
 * logout es destructivo —borra la memoria y los datos del dispositivo sin
 * vuelta atrás—, así que el dialog lo explicita y el botón usa el tono de
 * error. Para cuentas registradas es un aviso suave.
 */
export function LogoutDialog({ open, isEphemeral, onClose, onConfirm }: Props) {
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Cerrar sesión"
      description={isEphemeral ? "Tu cuenta es de invitado." : undefined}
    >
      <div className="flex flex-col gap-5">
        <p className="text-body text-[var(--color-ink)]">
          {isEphemeral
            ? "Como invitado, al cerrar sesión se borran tu memoria y tus datos de este dispositivo, y no se pueden recuperar."
            : "Vas a salir de tu cuenta. Vas a tener que volver a entrar para seguir."}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row-reverse">
          <Button
            variant="primary"
            fullWidth
            onClick={onConfirm}
            aria-label={isEphemeral ? "Cerrar sesión y borrar mis datos" : "Cerrar sesión"}
            className={
              isEphemeral
                ? "bg-[var(--color-error)] hover:opacity-90 disabled:hover:opacity-50"
                : undefined
            }
          >
            {isEphemeral ? "Cerrar sesión y borrar" : "Cerrar sesión"}
          </Button>
          <Button variant="ghost" fullWidth onClick={onClose}>
            Cancelar
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
