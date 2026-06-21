"""Connectivity del panel (``GET /v1/admin/connectivity``): tailnet + URLs para compartir.

Control plane del operador (no es métrica de negocio): permite compartir las superficies
de Ynara con otra máquina del tailnet de Tailscale — el panel admin, la app web, la API
OpenAI-compatible de Ollama y el chat de Open WebUI. El probe de Tailscale es READ-ONLY
(``tailscale status --json``, exec sin shell ni input del request) y degrada elegante si
el binario no está. Gate ``CurrentAdmin``.

Sin secretos (regla #4): nunca se ecoa ``str(exc)`` (solo ``type(exc).__name__``);
``tailnet_ip``/``hostname`` son la identidad de ESTA máquina en el tailnet del operador,
análogo al ``db_target`` (host) que expone ``GET /admin/system``.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import shutil

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.deps import CurrentAdmin
from app.schemas.admin_api import ConnectivityOut, ShareTarget, TailscaleStatus

router = APIRouter()

# Timeout del probe: el daemon responde en ms; 2s cubre un arranque lento sin
# colgar el endpoint. Constante (no setting): es un detalle interno de operación.
_TAILSCALE_PROBE_TIMEOUT_S = 2.0


def _pick_tailnet_ipv4(addrs: list[str]) -> str | None:
    """Primera IPv4 de ``Self.TailscaleIPs`` (trae IPv4 100.x + IPv6 fd7a:…).

    Valida con ``ipaddress`` en vez de heurística de string: si el binario cambiara
    el formato, descarta lo que no parsea como IP en vez de devolver basura.
    """
    for addr in addrs:
        try:
            if ipaddress.ip_address(addr).version == 4:
                return addr
        except ValueError:
            continue
    return None


async def _probe_tailscale(timeout_s: float = _TAILSCALE_PROBE_TIMEOUT_S) -> TailscaleStatus:
    """Estado del tailnet vía ``tailscale status --json`` (read-only, exec seguro).

    Degrada elegante: ``not_installed`` si el binario no está en el PATH, ``timeout``
    si el daemon no responde a tiempo, el ``BackendState`` (en minúsculas) si no está
    corriendo, o el nombre de la clase de excepción ante cualquier otro fallo. NUNCA
    ecoa ``str(exc)`` (regla #4).
    """
    binary = shutil.which("tailscale")
    if binary is None:
        return TailscaleStatus(up=False, detail="not_installed")

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            # reap + drena los fds del proceso muerto (evita ResourceWarning)
            await proc.communicate()
            return TailscaleStatus(up=False, detail="timeout")

        if proc.returncode != 0:
            return TailscaleStatus(up=False, detail=f"exit_{proc.returncode}")

        data = json.loads(stdout.decode("utf-8"))
        self_node = data.get("Self") or {}
        ipv4 = _pick_tailnet_ipv4(self_node.get("TailscaleIPs") or [])
        backend_state = data.get("BackendState")
        hostname = self_node.get("HostName")

        if backend_state != "Running" or ipv4 is None:
            return TailscaleStatus(
                up=False,
                hostname=hostname,
                tailnet_ip=ipv4,
                detail=str(backend_state or "no_ip").lower(),
            )
        return TailscaleStatus(up=True, hostname=hostname, tailnet_ip=ipv4, detail="up")
    except Exception as exc:
        return TailscaleStatus(up=False, detail=type(exc).__name__)


@router.get("/admin/connectivity", response_model=ConnectivityOut, status_code=200)
async def admin_connectivity(
    admin_id: CurrentAdmin,
) -> ConnectivityOut:
    """Estado del tailnet + URLs para compartir las superficies con otra máquina.

    Read-only, sin DB ni queries de negocio. Si el tailnet está arriba, arma las
    URLs de las superficies consumibles con el IP del tailnet + los puertos de
    config. Orden: panel admin (playground) y app web primero —lo que un invitado
    usa— y después la API ``/v1`` OpenAI-compatible y el chat de Open WebUI. Si el
    tailnet no está arriba, ``targets`` queda vacío (sin IP no hay URL alcanzable).
    Las URLs se arman aunque el servicio no esté levantado: el panel ofrece el
    destino; corré cada superficie que quieras compartir.
    """
    settings = get_settings()
    tailscale = await _probe_tailscale()

    targets: list[ShareTarget] = []
    if tailscale.up and tailscale.tailnet_ip:
        ip = tailscale.tailnet_ip
        targets = [
            ShareTarget(
                label="Panel admin",
                url=f"http://{ip}:{settings.admin_port}",
                port=settings.admin_port,
            ),
            ShareTarget(
                label="App web",
                url=f"http://{ip}:{settings.web_port}",
                port=settings.web_port,
            ),
            ShareTarget(
                label="API (OpenAI-compatible)",
                url=f"http://{ip}:{settings.ollama_api_port}/v1",
                port=settings.ollama_api_port,
            ),
            ShareTarget(
                label="Chat (Open WebUI)",
                url=f"http://{ip}:{settings.openwebui_port}",
                port=settings.openwebui_port,
            ),
        ]

    return ConnectivityOut(tailscale=tailscale, targets=targets)
