#!/usr/bin/env python3
"""Administración local del registro maestro de tiendas HardToCrack.

Los archivos tiendas.csv y eventos.csv contienen credenciales y están excluidos de Git.
"""

import argparse
import csv
import datetime as dt
import os
import pathlib
import re
import secrets
import tempfile


D = pathlib.Path(__file__).resolve().parent
TIENDAS = pathlib.Path(os.environ.get("REGISTRO_TIENDAS", D / "tiendas.csv"))
EVENTOS = pathlib.Path(os.environ.get("REGISTRO_EVENTOS", TIENDAS.with_name("eventos.csv")))
CAMPOS = [
    "codigo", "tienda", "titular", "territorio", "email_registrado", "telefono",
    "token", "pin", "estado", "alta", "ultima_rotacion", "baja", "notas",
]
E_CAMPOS = ["fecha_hora", "codigo", "accion", "estado", "detalle"]
CODIGO_RE = re.compile(r"^HTC-[A-Z]{3}-\d{3}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def leer(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir(path, campos, filas):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False, prefix=f".{path.name}."
    ) as f:
        temporal = pathlib.Path(f.name)
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in campos})
    os.replace(temporal, path)


def evento(codigo, accion, estado, detalle=""):
    filas = leer(EVENTOS)
    filas.append({
        "fecha_hora": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "codigo": codigo, "accion": accion, "estado": estado, "detalle": detalle,
    })
    escribir(EVENTOS, E_CAMPOS, filas)


def buscar(filas, codigo):
    codigo = codigo.upper()
    fila = next((x for x in filas if x.get("codigo", "").upper() == codigo), None)
    if not fila:
        raise SystemExit(f"No existe la tienda {codigo}.")
    return fila


def validar_codigo(codigo):
    codigo = codigo.upper()
    if not CODIGO_RE.fullmatch(codigo):
        raise SystemExit("El código debe tener el formato HTC-XXX-000.")
    return codigo


def alta(a):
    filas = leer(TIENDAS)
    codigo = validar_codigo(a.codigo)
    if any(x.get("codigo", "").upper() == codigo for x in filas):
        raise SystemExit(f"Ya existe la tienda {codigo}.")
    if not EMAIL_RE.fullmatch(a.email.lower()):
        raise SystemExit("El correo registrado no es válido.")
    hoy = dt.date.today().isoformat()
    fila = {
        "codigo": codigo, "tienda": a.tienda.strip(), "titular": a.titular.strip(),
        "territorio": a.territorio.strip(), "email_registrado": a.email.lower().strip(),
        "telefono": a.telefono.strip(), "token": secrets.token_hex(4),
        "pin": f"{secrets.randbelow(10000):04d}", "estado": "activa", "alta": hoy,
        "ultima_rotacion": hoy, "baja": "", "notas": a.notas.strip(),
    }
    filas.append(fila)
    escribir(TIENDAS, CAMPOS, filas)
    evento(codigo, "alta", "activa")
    print(f"Tienda: {codigo}\nToken:  {fila['token']}\nPIN:    {fila['pin']}")
    print(f"QR:     https://partners.hardtocrack.com/pedidos?t={codigo}&k={fila['token']}")


def listar(a):
    filas = leer(TIENDAS)
    if a.estado:
        filas = [x for x in filas if x.get("estado") == a.estado]
    if not filas:
        print("No hay tiendas registradas.")
        return
    for x in filas:
        print(f"{x.get('codigo','—'):12} {x.get('estado','—'):11} {x.get('tienda','—')} · {x.get('territorio','—')}")


def rotar(a):
    filas = leer(TIENDAS)
    codigo = validar_codigo(a.codigo)
    fila = buscar(filas, codigo)
    if fila.get("estado") != "activa":
        raise SystemExit("Solo se rota el token de una tienda activa.")
    fila["token"] = secrets.token_hex(4)
    fila["ultima_rotacion"] = dt.date.today().isoformat()
    escribir(TIENDAS, CAMPOS, filas)
    evento(codigo, "rotacion_token", fila["estado"], "El QR anterior queda invalidado")
    print(f"Nuevo token: {fila['token']}")
    print(f"Nuevo QR:    https://partners.hardtocrack.com/pedidos?t={codigo}&k={fila['token']}")


def revocar(a):
    filas = leer(TIENDAS)
    codigo = validar_codigo(a.codigo)
    fila = buscar(filas, codigo)
    fila["token"] = ""
    fila["estado"] = a.estado
    if a.estado == "baja":
        fila["baja"] = dt.date.today().isoformat()
    escribir(TIENDAS, CAMPOS, filas)
    evento(codigo, "revocacion", a.estado, a.motivo.strip())
    print(f"{codigo} queda en estado {a.estado}; el enlace QR anterior ya no valida.")


def activar(a):
    filas = leer(TIENDAS)
    codigo = validar_codigo(a.codigo)
    fila = buscar(filas, codigo)
    fila["estado"] = "activa"
    fila["baja"] = ""
    fila["token"] = secrets.token_hex(4)
    fila["ultima_rotacion"] = dt.date.today().isoformat()
    escribir(TIENDAS, CAMPOS, filas)
    evento(codigo, "reactivacion", "activa", "Se genera un token nuevo")
    print(f"Token: {fila['token']}\nPIN:   {fila['pin']}")
    print(f"QR:    https://partners.hardtocrack.com/pedidos?t={codigo}&k={fila['token']}")


def parser():
    p = argparse.ArgumentParser(description="Registro maestro de tiendas HardToCrack")
    s = p.add_subparsers(dest="comando", required=True)
    a = s.add_parser("alta", help="dar de alta una tienda")
    a.add_argument("codigo"); a.add_argument("--tienda", required=True); a.add_argument("--titular", required=True)
    a.add_argument("--territorio", required=True); a.add_argument("--email", required=True)
    a.add_argument("--telefono", default=""); a.add_argument("--notas", default=""); a.set_defaults(func=alta)
    a = s.add_parser("listar", help="listar tiendas"); a.add_argument("--estado", choices=["activa", "suspendida", "baja"]); a.set_defaults(func=listar)
    a = s.add_parser("rotar", help="rotar token y generar un QR nuevo"); a.add_argument("codigo"); a.set_defaults(func=rotar)
    a = s.add_parser("revocar", help="invalidar token y suspender o dar de baja")
    a.add_argument("codigo"); a.add_argument("--estado", choices=["suspendida", "baja"], default="suspendida"); a.add_argument("--motivo", default=""); a.set_defaults(func=revocar)
    a = s.add_parser("activar", help="reactivar con un token nuevo"); a.add_argument("codigo"); a.set_defaults(func=activar)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
