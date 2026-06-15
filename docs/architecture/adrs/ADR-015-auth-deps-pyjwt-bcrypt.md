# ADR-015: Librería JWT = PyJWT (sale python-jose); bcrypt directo (sale passlib)

> **Refina** [ADR-011](./ADR-011-auth-layering-criterion.md) (capas de auth): la
> pieza "JWT + bcrypt" de `app/core/security.py` cambia de implementación sin
> tocar el criterio de layering ni los contratos de auth.

## Estado

Aceptado

<!-- Aprobado por Mateo García (operador humano) el 2026-06-15 como parte de la
     remediación de la auditoría backend (migración de deps de seguridad). -->

## Fecha

2026-06-15

## Contexto

`app/core/security.py` firma/verifica JWTs (HS256) y hashea contraseñas. Hasta
ahora dependía de dos librerías problemáticas:

- **`python-jose[cryptography]`**: sin mantenimiento activo desde ~2021 y con
  **CVE-2024-33664** (denial of service por consumo de memoria al decodificar un
  JWE con contenido comprimido anidado). Ynara la usaba **solo** para HS256
  simétrico (`jwt.encode` / `jwt.decode`), nunca para JWE, así que la exposición
  era baja, pero arrastraba un árbol de transitivas asimétricas (`ecdsa`, `rsa`,
  `pyasn1`) que Ynara no usa.
- **`passlib[bcrypt]`**: declarada pero **ya no usada en el código** —
  `security.py` hashea con `bcrypt.hashpw`/`checkpw` directo desde que se detectó
  que passlib 1.7.4 (último release, 2020) no es compatible con bcrypt 4.x. Era
  una dependencia muerta que además dejaba a `bcrypt` como transitiva implícita.

La auditoría backend marcó ambas como deuda de seguridad/higiene de
dependencias. El comentario de `_decode_token` ya anticipaba la migración
(documentaba la diferencia `require_exp` de jose vs `require: [...]` de PyJWT).

## Decisión

### D1 — Librería JWT = **PyJWT** (`pyjwt>=2.9.0`)

Se reemplaza `python-jose` por **PyJWT**. Ynara usa **solo HS256 simétrico**, así
que NO hace falta el extra `[crypto]` (que solo aporta `cryptography` para
RS*/ES*/PS*/EdDSA): `pyjwt` pelado alcanza. La API es casi idéntica
(`jwt.encode(payload, key, algorithm=...) -> str`, `jwt.decode(...)`); el único
cambio funcional es la forma del `options` y la jerarquía de excepciones (D3).

### D2 — `bcrypt` pasa a dependencia de primer nivel (sale `passlib`)

Se elimina `passlib[bcrypt]` (muerta) y se declara **`bcrypt>=4.1.0`** como
dependencia directa, porque el código ya la usa directo. Sin cambio de
comportamiento: el hashing/verificación de contraseñas era ya `bcrypt` puro.

### D3 — Equivalencias de API (sin cambio de comportamiento observable)

| Aspecto | python-jose | PyJWT 2.x |
| --- | --- | --- |
| `encode()` retorna | `str` | `str` (igual) |
| Exigir claim `exp` | `options={"require_exp": True}` | `options={"require": ["exp"]}` |
| Verificar expiración | `{"verify_exp": True}` | `{"verify_exp": True}` (igual) |
| Excepción base a capturar | `jose.JWTError` | `jwt.PyJWTError` |

`_decode_token` captura **`jwt.PyJWTError`** (la raíz de la jerarquía: cubre
firma inválida, expirado, malformado y claim requerido faltante) y la reenvía
como el `InvalidTokenError` interno con string estático `"token inválido"`
(regla #4: el detalle de PyJWT queda solo en `__cause__`, nunca en la respuesta
ni en un log). **Trampa evitada**: la forma vieja `{"require_exp": True}` PyJWT
la **ignora en silencio** — el test `test_token_without_exp_rejected` bloquea esa
regresión (un token sin `exp` debe seguir siendo rechazado).

### D4 — La CVE de python-jose ya estaba mitigada (y ahora eliminada)

CVE-2024-33664 aplica al path JWE, que Ynara nunca ejerció (solo HS256 JWS), y
`jwt.decode` siempre se llama con `algorithms=[settings.jwt_algorithm]`
explícito (no acepta `alg` arbitrario del token → sin confusión de algoritmo).
La migración la elimina de raíz al sacar la librería.

## Consecuencias positivas

- **−5 paquetes** del árbol de dependencias: `python-jose`, `passlib`, y las
  transitivas asimétricas que jose arrastraba (`ecdsa`, `rsa`, `pyasn1`). Menos
  superficie de ataque y de supply-chain.
- Librería JWT **mantenida** (PyJWT) en vez de una abandonada.
- PyJWT 2.13 **advierte** (`InsecureKeyLengthWarning`, RFC 7518) cuando la clave
  HMAC tiene <32 bytes: defensa en profundidad que se alinea con el fail-fast de
  prod (`_reject_weak_jwt_secret_in_prod` ya exige ≥32 chars). Los secrets de los
  tests se subieron a ≥32 bytes para reflejar ese piso y dejar el suite unit sin
  ruido.
- `bcrypt` deja de ser una transitiva implícita: la intención del código (hashing
  con bcrypt directo) queda declarada en `pyproject.toml`.

## Consecuencias negativas / mitigaciones

- Cambio de librería en código de auth (security-critical). **Mitigación**: los
  tests de `security.py` lockean el comportamiento (round-trip, tampered,
  expirado, garbage, exp requerido, type/jti anti-falsificación, compat de tokens
  pre-#63) y pasan idénticos contra PyJWT; validado además contra el path real
  HTTP+DB (46 tests de integración de auth).
- Tokens en vuelo: PyJWT decodifica sin problema los JWT HS256 minteados por jose
  (es el mismo estándar), así que no hay invalidación de sesiones en el deploy.

## Relación con otros ADRs

- **Refina** [ADR-011](./ADR-011-auth-layering-criterion.md): la pieza
  "JWT (PyJWT) + bcrypt" de `app/core/security.py` cambia de implementación; el
  criterio de capas de auth y los contratos (`create_*_token`, `verify_token`,
  `hash_password`, `verify_password`) quedan intactos.

## Fuentes

- CVE-2024-33664 (python-jose, JWE DoS): GHSA-cjwg-qfpm-7377.
- PyJWT 2.x docs: `options={"require": [...]}`, jerarquía `PyJWTError`, HS256 sin
  extra `[crypto]`.
- RFC 7518 §3.2 (longitud mínima de clave HMAC para HS256).
- `app/core/config.py::_reject_weak_jwt_secret_in_prod` (piso de 32 chars en prod).
