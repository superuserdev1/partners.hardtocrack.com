#!/usr/bin/env python3
"""Backend de /pedidos · HardToCrack Partners.

Registra pedidos, separa los datos comerciales de los personales, envía acuses y ofrece un
panel interno protegido para aceptar o rechazar pedidos. No usa servicios externos de datos.
"""

import csv
import datetime as dt
import os
import pathlib
import random
import re
import secrets
import smtplib
import tempfile
import threading
from email.message import EmailMessage
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field


D = pathlib.Path(__file__).resolve().parent
REG = pathlib.Path(os.environ.get("REGISTRO_TIENDAS", D / "registro" / "tiendas.csv"))
OUT = pathlib.Path(os.environ.get("REGISTRO_PEDIDOS", D / "registros"))
OUT.mkdir(parents=True, exist_ok=True)
MAILDIR = OUT / "salida_correo"

BUZON = os.environ.get("BUZON_PEDIDOS", "pedidos@hardtocrack.com")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

COMERCIAL = OUT / "pedidos_comercial.csv"
DATOS = OUT / "pedidos_datos.csv"
EVENTOS = OUT / "pedidos_eventos.csv"

C_CAMPOS = [
    "referencia", "fecha_hora", "codigo_tienda", "modelo", "estado_equipo", "pack",
    "accesorios", "precio", "forma_pago", "estado", "decision_fecha", "decision_motivo",
]
D_CAMPOS = [
    "referencia", "fecha_hora", "codigo_tienda", "cliente", "contacto",
    "email_tienda", "observaciones",
]
E_CAMPOS = [
    "fecha_hora", "referencia", "accion", "estado_anterior", "estado_nuevo",
    "operador", "motivo",
]

MODELOS = {
    "Google Pixel 8a", "Google Pixel 9a", "Google Pixel 10a", "Google Pixel 10 Pro",
    "Otro Pixel compatible",
}
ESTADOS_EQUIPO = {"Nuevo", "Reacondicionado"}
PACKS = {"Essential", "Privacy", "Elite"}
FORMAS_PAGO = {
    "Cobro en tienda (mandato activo)", "Pago a HardToCrack", "Pendiente de confirmar",
}
CODIGO_RE = re.compile(r"^HTC-[A-Z]{3}-\d{3}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MES_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DATA_LOCK = threading.RLock()


app = FastAPI(title="HardToCrack · Registro de pedidos", docs_url=None, redoc_url=None)

allowed_origins = [x.strip() for x in os.environ.get("ALLOWED_ORIGINS", "").split(",") if x.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )


@app.middleware("http")
async def cabeceras_seguras(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
        "img-src 'self' data:; connect-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; form-action 'self'"
    )
    if request.url.path.startswith("/api/admin") or request.url.path.startswith("/pedidos/admin"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


class Pedido(BaseModel):
    codigo_tienda: str = Field(default="", max_length=20)
    token: str = Field(default="", max_length=64)
    pin: str = Field(default="", max_length=8)
    modelo: str = Field(default="", max_length=80)
    estado: str = Field(default="", max_length=30)
    pack: str = Field(default="", max_length=30)
    precio: str = Field(default="", max_length=20)
    accesorios: str = Field(default="", max_length=300)
    cliente: str = Field(default="", max_length=120)
    contacto: str = Field(default="", max_length=160)
    pago: str = Field(default="", max_length=80)
    email_tienda: str = Field(default="", max_length=160)
    observaciones: str = Field(default="", max_length=800)
    confirmacion: bool = False


class Decision(BaseModel):
    estado: Literal["aceptado", "rechazado"]
    motivo: str = Field(default="", max_length=500)
    operador: str = Field(default="Administración HTC", max_length=80)


def limpiar(valor: str) -> str:
    return " ".join((valor or "").strip().split())


def leer_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir_csv_atomico(path: pathlib.Path, campos: list[str], filas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False, prefix=f".{path.name}."
    ) as f:
        temporal = pathlib.Path(f.name)
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({campo: fila.get(campo, "") for campo in campos})
    os.replace(temporal, path)


def agregar(path: pathlib.Path, campos: list[str], fila: dict) -> None:
    filas = leer_csv(path)
    filas.append(fila)
    escribir_csv_atomico(path, campos, filas)


def tiendas() -> dict[str, dict]:
    if not REG.exists():
        return {}
    with REG.open(encoding="utf-8", newline="") as f:
        return {r.get("codigo", "").upper(): r for r in csv.DictReader(f) if r.get("codigo")}


def validar_tienda(codigo: str, token: str, pin: str):
    codigo = limpiar(codigo).upper()
    t = tiendas().get(codigo)
    if not t:
        return None, "Código de tienda no reconocido."
    if t.get("estado", "").strip().lower() != "activa":
        return None, "Tu tienda no está operativa. Contacta con partners@hardtocrack.com."
    if token:
        if not t.get("token") or not secrets.compare_digest(t["token"], token.strip()):
            return None, "Enlace no válido o caducado. Usa el QR actual de tu mostrador."
        return t, None
    if pin:
        if not t.get("pin") or not secrets.compare_digest(t["pin"], pin.strip()):
            return None, "PIN incorrecto."
        return t, None
    return None, "Falta el token del enlace o el PIN de tu ficha."


def validar_pedido(p: Pedido) -> str | None:
    if not CODIGO_RE.fullmatch(limpiar(p.codigo_tienda).upper()):
        return "El código de tienda no tiene un formato válido."
    if p.modelo not in MODELOS:
        return "Selecciona un modelo válido."
    if p.estado not in ESTADOS_EQUIPO:
        return "Selecciona un estado válido para el equipo."
    if p.pack not in PACKS:
        return "Selecciona un pack válido."
    if p.pago not in FORMAS_PAGO:
        return "Selecciona una forma de pago válida."
    if not limpiar(p.cliente):
        return "Falta el nombre del cliente."
    if not limpiar(p.contacto):
        return "Falta el contacto del cliente."
    if not EMAIL_RE.fullmatch(limpiar(p.email_tienda).lower()):
        return "El correo de la tienda no es válido."
    try:
        precio = float(p.precio.replace(",", "."))
        if precio <= 0 or precio > 20000:
            raise ValueError
    except ValueError:
        return "El precio aplicado no es válido."
    if not p.confirmacion:
        return "Debes confirmar la declaración antes de registrar el pedido."
    return None


def nueva_referencia(filas: list[dict]) -> str:
    hoy = dt.date.today()
    usadas = {r.get("referencia") for r in filas}
    while True:
        ref = f"HTC-{hoy:%y%m}-{random.randint(1, 9999):04d}"
        if ref not in usadas:
            return ref


def cuerpo_acuse(ref: str, p: Pedido, tienda: dict, ahora: str, completo: bool) -> str:
    lineas = [
        "HardToCrack · Acuse de registro de pedido", "",
        f"Referencia        {ref}",
        f"Fecha y hora      {ahora}",
        f"Tienda            {tienda.get('tienda', '—')} ({tienda.get('codigo', '—')})", "",
        f"Modelo            {p.modelo} · {p.estado}",
        f"Pack              {p.pack}",
        f"Accesorios        {limpiar(p.accesorios) or '—'}",
        f"Precio aplicado   {float(p.precio.replace(',', '.')):.2f} €",
        f"Forma de pago     {p.pago}",
    ]
    if completo:
        lineas += [
            "", f"Cliente           {limpiar(p.cliente)}", f"Contacto          {limpiar(p.contacto)}",
            f"Observaciones     {limpiar(p.observaciones) or '—'}",
        ]
    else:
        lineas += [
            "", "Los datos del cliente constan en el registro de HardToCrack y no se",
            "reproducen en esta copia.",
        ]
    lineas += [
        "", "Recibirás la aceptación o el rechazo en dos días hábiles. El contrato con el",
        "cliente queda confirmado cuando HardToCrack lo acepta por un medio duradero.",
        "", "Este acuse acredita el registro previo del lead a efectos de atribución.",
        "Las condiciones económicas aplicables son las del Anexo II de tu Acuerdo Marco.",
        "", "HardToCrack · partners@hardtocrack.com · 910 79 22 96",
    ]
    return "\n".join(lineas)


def cuerpo_decision(ref: str, estado: str, motivo: str, tienda: dict) -> str:
    decision = "ACEPTADO" if estado == "aceptado" else "RECHAZADO"
    lineas = [
        "HardToCrack · Resolución de pedido", "", f"Referencia        {ref}",
        f"Tienda            {tienda.get('tienda', '—')} ({tienda.get('codigo', '—')})",
        f"Estado            {decision}",
    ]
    if motivo:
        lineas += [f"Motivo            {motivo}"]
    lineas += ["", "Conserva este mensaje como constancia de la resolución.", "", "HardToCrack"]
    return "\n".join(lineas)


def enviar(destino: str, asunto: str, texto: str) -> str:
    host = os.environ.get("SMTP_HOST")
    if not host:
        MAILDIR.mkdir(parents=True, exist_ok=True)
        nombre = re.sub(r"[^a-z0-9]", "_", destino.lower())
        f = MAILDIR / f"{dt.datetime.now():%Y%m%d-%H%M%S}_{secrets.token_hex(2)}_{nombre}.txt"
        f.write_text(f"Para: {destino}\nAsunto: {asunto}\n\n{texto}", encoding="utf-8")
        return f"guardado:{f.name}"
    m = EmailMessage()
    m["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    m["To"] = destino
    m["Subject"] = asunto
    m.set_content(texto)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=20) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(m)
    return "enviado"


def exigir_admin(x_admin_token: str = Header(default="")) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="El acceso interno todavía no está configurado.")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Credencial interna no válida.")


def limite_laborable(fecha_iso: str, dias: int = 2) -> str:
    fecha = dt.datetime.fromisoformat(fecha_iso).date()
    añadidos = 0
    while añadidos < dias:
        fecha += dt.timedelta(days=1)
        if fecha.weekday() < 5:
            añadidos += 1
    return fecha.isoformat()


@app.get("/api/salud")
def salud():
    t = tiendas()
    return {
        "ok": True,
        "tiendas": len(t),
        "activas": sum(1 for r in t.values() if r.get("estado", "").lower() == "activa"),
        "correo": "smtp" if os.environ.get("SMTP_HOST") else "archivo",
        "administracion": "configurada" if ADMIN_TOKEN else "pendiente",
    }


@app.post("/api/pedido")
def crear(p: Pedido):
    p.codigo_tienda = limpiar(p.codigo_tienda).upper()
    err = validar_pedido(p)
    if err:
        return JSONResponse({"ok": False, "error": err}, status_code=400)
    tienda, err = validar_tienda(p.codigo_tienda, p.token, p.pin)
    if err:
        return JSONResponse({"ok": False, "error": err}, status_code=400)

    destino_tienda = limpiar(tienda.get("email_registrado", "")).lower() or limpiar(p.email_tienda).lower()
    ahora = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    precio = f"{float(p.precio.replace(',', '.')):.2f}"

    with DATA_LOCK:
        comerciales = leer_csv(COMERCIAL)
        ref = nueva_referencia(comerciales)
        comerciales.append({
            "referencia": ref, "fecha_hora": ahora, "codigo_tienda": tienda.get("codigo", p.codigo_tienda),
            "modelo": p.modelo, "estado_equipo": p.estado, "pack": p.pack,
            "accesorios": limpiar(p.accesorios), "precio": precio, "forma_pago": p.pago,
            "estado": "pendiente de aceptacion", "decision_fecha": "", "decision_motivo": "",
        })
        personales = leer_csv(DATOS)
        personales.append({
            "referencia": ref, "fecha_hora": ahora, "codigo_tienda": tienda.get("codigo", p.codigo_tienda),
            "cliente": limpiar(p.cliente), "contacto": limpiar(p.contacto),
            "email_tienda": destino_tienda, "observaciones": limpiar(p.observaciones),
        })
        escribir_csv_atomico(COMERCIAL, C_CAMPOS, comerciales)
        escribir_csv_atomico(DATOS, D_CAMPOS, personales)

    avisos = []
    if destino_tienda != limpiar(p.email_tienda).lower():
        avisos.append("El acuse se ha enviado al correo registrado en el alta de la tienda.")
    asunto = f"[{ref}] Pedido registrado · {tienda.get('codigo', p.codigo_tienda)}"
    try:
        enviar(BUZON, asunto, cuerpo_acuse(ref, p, tienda, ahora, completo=True))
        enviar(
            destino_tienda, f"Acuse de pedido {ref} · HardToCrack",
            cuerpo_acuse(ref, p, tienda, ahora, completo=False),
        )
    except Exception:
        avisos.append("El pedido quedó registrado, pero el envío del acuse necesita revisión.")

    return {"ok": True, "referencia": ref, "avisos": avisos}


@app.get("/api/admin/pedidos", dependencies=[Depends(exigir_admin)])
def listar_pedidos(mes: str = Query(default_factory=lambda: dt.date.today().strftime("%Y-%m"))):
    if not MES_RE.fullmatch(mes):
        raise HTTPException(status_code=400, detail="Mes no válido; usa AAAA-MM.")
    with DATA_LOCK:
        comerciales = [r for r in leer_csv(COMERCIAL) if r.get("fecha_hora", "").startswith(mes)]
        personales = {r.get("referencia"): r for r in leer_csv(DATOS)}
    hoy = dt.date.today().isoformat()
    pedidos = []
    for c in comerciales:
        p = personales.get(c.get("referencia"), {})
        limite = limite_laborable(c["fecha_hora"]) if c.get("fecha_hora") else ""
        pedidos.append({
            **c,
            "cliente": p.get("cliente", ""), "contacto": p.get("contacto", ""),
            "email_tienda": p.get("email_tienda", ""), "observaciones": p.get("observaciones", ""),
            "fecha_limite": limite,
            "vencido": bool(limite and limite < hoy and c.get("estado") == "pendiente de aceptacion"),
        })
    pedidos.sort(key=lambda x: x.get("fecha_hora", ""), reverse=True)
    estados = [p.get("estado", "") for p in pedidos]
    return {
        "ok": True, "mes": mes,
        "contadores": {
            "total": len(pedidos),
            "pendientes": estados.count("pendiente de aceptacion"),
            "aceptados": estados.count("aceptado"),
            "rechazados": estados.count("rechazado"),
            "vencidos": sum(1 for p in pedidos if p["vencido"]),
        },
        "pedidos": pedidos,
    }


@app.post("/api/admin/pedidos/{referencia}/decision", dependencies=[Depends(exigir_admin)])
def decidir(referencia: str, decision: Decision):
    referencia = referencia.strip().upper()
    if not re.fullmatch(r"HTC-\d{4}-\d{4}", referencia):
        raise HTTPException(status_code=400, detail="Referencia no válida.")
    ahora = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    motivo = limpiar(decision.motivo)
    operador = limpiar(decision.operador) or "Administración HTC"
    if decision.estado == "rechazado" and not motivo:
        raise HTTPException(status_code=400, detail="El rechazo requiere un motivo.")

    with DATA_LOCK:
        comerciales = leer_csv(COMERCIAL)
        fila = next((r for r in comerciales if r.get("referencia") == referencia), None)
        if not fila:
            raise HTTPException(status_code=404, detail="Pedido no encontrado.")
        anterior = fila.get("estado", "")
        if anterior != "pendiente de aceptacion":
            raise HTTPException(status_code=409, detail=f"El pedido ya figura como {anterior}.")
        fila["estado"] = decision.estado
        fila["decision_fecha"] = ahora
        fila["decision_motivo"] = motivo
        escribir_csv_atomico(COMERCIAL, C_CAMPOS, comerciales)
        agregar(EVENTOS, E_CAMPOS, {
            "fecha_hora": ahora, "referencia": referencia, "accion": "decision",
            "estado_anterior": anterior, "estado_nuevo": decision.estado,
            "operador": operador, "motivo": motivo,
        })
        personal = next((r for r in leer_csv(DATOS) if r.get("referencia") == referencia), {})

    tienda = tiendas().get(fila.get("codigo_tienda", ""), {"codigo": fila.get("codigo_tienda", "")})
    texto = cuerpo_decision(referencia, decision.estado, motivo, tienda)
    avisos = []
    destinatarios = {personal.get("email_tienda", "")}
    contacto = personal.get("contacto", "").strip()
    if EMAIL_RE.fullmatch(contacto):
        destinatarios.add(contacto.lower())
    destinatarios.discard("")
    for destino in destinatarios:
        try:
            enviar(destino, f"Resolución del pedido {referencia} · HardToCrack", texto)
        except Exception:
            avisos.append(f"No se pudo enviar la resolución a {destino}.")
    if contacto and not EMAIL_RE.fullmatch(contacto):
        avisos.append("El contacto del cliente no es un correo; requiere comunicación por el canal registrado.")
    return {"ok": True, "referencia": referencia, "estado": decision.estado, "avisos": avisos}


@app.get("/pedidos", include_in_schema=False)
def pedidos_sin_barra(request: Request):
    destino = "/pedidos/"
    if request.url.query:
        destino += f"?{request.url.query}"
    return RedirectResponse(url=destino, status_code=308)


@app.get("/pedidos/", include_in_schema=False)
def formulario_pedidos():
    return FileResponse(D / "index.html", headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/pedidos/admin", include_in_schema=False)
def panel_interno():
    return FileResponse(D / "admin.html", headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/pedidos/ht-logo.svg", include_in_schema=False)
def logo_pedidos():
    return FileResponse(D / "ht-logo.svg", media_type="image/svg+xml")
