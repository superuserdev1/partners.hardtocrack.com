#!/usr/bin/env python3
"""Backend de /pedidos · HardToCrack.

Valida la pareja código de tienda + token (o código + PIN), genera la referencia del pedido,
envía el doble acuse (pedidos@hardtocrack.com y correo de la tienda) y guarda dos registros
separados:

  registros/pedidos_comercial.csv  → sin datos personales: referencia, fecha, tienda, modelo,
                                     pack, precio, estado. Es el que usas para comisiones.
  registros/pedidos_datos.csv      → datos del cliente, solo lo necesario para ejecutar el
                                     pedido. Se depura según el plazo de conservación fijado.

Variables de entorno para el envío de correo (si faltan, el acuse se guarda en
registros/salida_correo/ en lugar de enviarse):

  SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASS SMTP_FROM
  BUZON_PEDIDOS   (por defecto pedidos@hardtocrack.com)

Arranque:  uvicorn server:app --host 0.0.0.0 --port 8080
"""
import csv, datetime as dt, os, pathlib, random, re, secrets, smtplib
from email.message import EmailMessage

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

D = pathlib.Path(__file__).parent
REG = pathlib.Path(os.environ.get("REGISTRO_TIENDAS", D.parent / "registro" / "tiendas.csv"))
OUT = D / "registros"
OUT.mkdir(exist_ok=True)
MAILDIR = OUT / "salida_correo"

BUZON = os.environ.get("BUZON_PEDIDOS", "pedidos@hardtocrack.com")

COMERCIAL = OUT / "pedidos_comercial.csv"
DATOS = OUT / "pedidos_datos.csv"

C_CAMPOS = ["referencia", "fecha_hora", "codigo_tienda", "modelo", "estado_equipo", "pack",
            "accesorios", "precio", "forma_pago", "estado"]
D_CAMPOS = ["referencia", "fecha_hora", "codigo_tienda", "cliente", "contacto",
            "email_tienda", "observaciones"]

app = FastAPI(title="HardToCrack · Registro de pedidos")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


class Pedido(BaseModel):
    codigo_tienda: str = ""
    token: str = ""
    pin: str = ""
    modelo: str = ""
    estado: str = ""
    pack: str = ""
    precio: str = ""
    accesorios: str = ""
    cliente: str = ""
    contacto: str = ""
    pago: str = ""
    email_tienda: str = ""
    observaciones: str = ""


# ─────────────────── registro de tiendas ───────────────────
def tiendas():
    if not REG.exists():
        return {}
    with REG.open(encoding="utf-8", newline="") as f:
        return {r["codigo"].upper(): r for r in csv.DictReader(f)}


def validar(codigo, token, pin):
    t = tiendas().get(codigo.upper())
    if not t:
        return None, "Código de tienda no reconocido."
    if t["estado"] != "activa":
        return None, "Tu tienda no está operativa. Contacta con partners@hardtocrack.com."
    if token:
        if not t["token"] or not secrets.compare_digest(t["token"], token):
            return None, "Enlace no válido o caducado. Usa el QR actual de tu mostrador."
        return t, None
    if pin:
        if not secrets.compare_digest(t["pin"], pin):
            return None, "PIN incorrecto."
        return t, None
    return None, "Falta el token del enlace o el PIN de tu ficha."


# ─────────────────── referencia y almacenamiento ───────────────────
def referencia():
    hoy = dt.date.today()
    usadas = set()
    if COMERCIAL.exists():
        with COMERCIAL.open(encoding="utf-8", newline="") as f:
            usadas = {r["referencia"] for r in csv.DictReader(f)}
    while True:
        ref = f"HTC-{hoy:%y%m}-{random.randint(1, 9999):04d}"
        if ref not in usadas:
            return ref


def guardar(path, campos, fila):
    nuevo = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


# ─────────────────── correo ───────────────────
def cuerpo(ref, p, tienda, ahora, completo):
    lineas = [
        "HardToCrack · Acuse de registro de pedido", "",
        f"Referencia        {ref}",
        f"Fecha y hora      {ahora}",
        f"Tienda            {tienda['tienda']} ({tienda['codigo']})", "",
        f"Modelo            {p.modelo} · {p.estado}",
        f"Pack              {p.pack}",
        f"Accesorios        {p.accesorios or '—'}",
        f"Precio aplicado   {p.precio} €",
        f"Forma de pago     {p.pago}",
    ]
    if completo:
        lineas += ["", f"Cliente           {p.cliente}",
                   f"Contacto          {p.contacto}",
                   f"Observaciones     {p.observaciones or '—'}"]
    else:
        lineas += ["", "Los datos del cliente constan en el registro de HardToCrack y no se",
                   "reproducen en esta copia."]
    lineas += ["", "Recibirás la aceptación o el rechazo en dos días hábiles. El contrato con el",
               "cliente queda confirmado cuando HardToCrack lo acepta por un medio duradero.",
               "", "Este acuse acredita el registro previo del lead a efectos de atribución.",
               "Las condiciones económicas aplicables son las del Anexo II de tu Acuerdo Marco.",
               "", "HardToCrack · partners@hardtocrack.com · 910 79 22 96"]
    return "\n".join(lineas)


def enviar(destino, asunto, texto):
    host = os.environ.get("SMTP_HOST")
    if not host:
        MAILDIR.mkdir(exist_ok=True)
        f = MAILDIR / f"{dt.datetime.now():%Y%m%d-%H%M%S}_{secrets.token_hex(2)}_{re.sub(r'[^a-z0-9]', '_', destino.lower())}.txt"
        f.write_text(f"Para: {destino}\nAsunto: {asunto}\n\n{texto}", encoding="utf-8")
        return f"guardado:{f.name}"
    m = EmailMessage()
    m["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    m["To"] = destino
    m["Subject"] = asunto
    m.set_content(texto)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(m)
    return "enviado"


# ─────────────────── endpoints ───────────────────
@app.get("/api/salud")
def salud():
    t = tiendas()
    return {"ok": True, "tiendas": len(t),
            "activas": sum(1 for r in t.values() if r["estado"] == "activa"),
            "correo": "smtp" if os.environ.get("SMTP_HOST") else "archivo"}


@app.post("/api/pedido")
def crear(p: Pedido):
    tienda, err = validar(p.codigo_tienda, p.token, p.pin)
    if err:
        return JSONResponse({"ok": False, "error": err}, status_code=400)

    for campo, nombre in (("modelo", "modelo"), ("estado", "estado del equipo"),
                          ("pack", "pack"), ("precio", "precio"), ("cliente", "cliente"),
                          ("contacto", "contacto"), ("pago", "forma de pago"),
                          ("email_tienda", "correo de tu tienda")):
        if not getattr(p, campo):
            return JSONResponse({"ok": False, "error": f"Falta el campo {nombre}."},
                                status_code=400)

    # el acuse va siempre al correo registrado en el alta, no al que se teclee
    destino_tienda = tienda["email_registrado"] or p.email_tienda
    ref = referencia()
    ahora = dt.datetime.now().isoformat(timespec="seconds")

    guardar(COMERCIAL, C_CAMPOS, {"referencia": ref, "fecha_hora": ahora,
                                  "codigo_tienda": tienda["codigo"], "modelo": p.modelo,
                                  "estado_equipo": p.estado, "pack": p.pack,
                                  "accesorios": p.accesorios, "precio": p.precio,
                                  "forma_pago": p.pago, "estado": "pendiente de aceptacion"})
    guardar(DATOS, D_CAMPOS, {"referencia": ref, "fecha_hora": ahora,
                              "codigo_tienda": tienda["codigo"], "cliente": p.cliente,
                              "contacto": p.contacto, "email_tienda": destino_tienda,
                              "observaciones": p.observaciones})

    asunto = f"[{ref}] Pedido registrado · {tienda['codigo']}"
    enviar(BUZON, asunto, cuerpo(ref, p, tienda, ahora, completo=True))
    enviar(destino_tienda, f"Acuse de pedido {ref} · HardToCrack",
           cuerpo(ref, p, tienda, ahora, completo=False))

    return {"ok": True, "referencia": ref,
            "aviso_email": None if destino_tienda == p.email_tienda
            else "El acuse se ha enviado al correo registrado en tu alta."}
