import { redirect } from "next/navigation";

/**
 * Back-compat: la home se renombró a `/hoy` (tab Hoy dentro del app shell,
 * build-plan §3.1). `/home` queda como redirect permanente para no romper
 * links viejos. Las referencias internas ya apuntan a `/hoy`.
 */
export default function HomeRedirect() {
  redirect("/hoy");
}
