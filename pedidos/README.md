# /pedidos · HardToCrack Partners

Canal autorizado para que una tienda registre un pedido antes de que el cliente salga. Valida la
tienda por QR con token o por código y PIN, genera una referencia, separa datos comerciales y
personales y deja constancia por correo.

## Qué incluye

- `index.html`: formulario responsive en español.
- `ht-logo.svg`: geometría del vector corporativo con el gradiente web `#23B8FF → #20E38C`.
- `server.py`: API FastAPI, archivos CSV, acuses y panel de decisión.
- `admin.html`: panel interno con contadores mensuales y aceptación/rechazo.
- `registro/tiendas.py`: altas, listado, rotación, suspensión, baja y reactivación de tiendas.
- `deploy/`: ejemplos para Nginx, Caddy y systemd.
- `.env.example`: variables necesarias sin credenciales reales.

Los desplegables tienen colores explícitos para que sus opciones sean legibles en Chrome y Edge
en Windows, tanto con tema claro como oscuro.

## Puesta en marcha local

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn server:app --host 127.0.0.1 --port 8080
```

Abrir:

- Formulario: `http://127.0.0.1:8080/pedidos/`
- Gestión interna: `http://127.0.0.1:8080/pedidos/admin`
- Salud: `http://127.0.0.1:8080/api/salud`

## Registro maestro de tiendas

`registro/tiendas.csv` es la fuente de verdad y nunca se sube al repositorio. Para crear la primera
tienda:

```bash
python registro/tiendas.py alta HTC-MAD-001 \
  --tienda "Nombre comercial" \
  --titular "Responsable" \
  --territorio "Madrid Centro" \
  --email "tienda@ejemplo.es"
```

La orden devuelve el token, el PIN y la URL exacta que se convierte en QR. Operaciones adicionales:

```bash
python registro/tiendas.py listar
python registro/tiendas.py rotar HTC-MAD-001
python registro/tiendas.py revocar HTC-MAD-001 --estado suspendida --motivo "Fin de pruebas"
python registro/tiendas.py activar HTC-MAD-001
```

Rotar o reactivar genera un token nuevo y obliga a sustituir el QR. Revocar vacía el token; los
pedidos históricos permanecen intactos.

## Rutas de tienda

```text
https://partners.hardtocrack.com/pedidos?t=HTC-MAD-001&k=7f2c9be4
```

Con `t` y `k`, el bloque manual se oculta. Como respaldo se usa el código más el PIN de cuatro
dígitos. Solo se admiten tiendas con estado `activa`.

## Administración y resoluciones

`/pedidos/admin` solicita `ADMIN_TOKEN`, que se conserva solo durante la sesión del navegador. El
panel muestra total, pendientes, aceptados, rechazados y fuera de plazo por mes. La resolución:

1. cambia el estado del registro comercial;
2. anota fecha, operador y motivo en `pedidos_eventos.csv`;
3. envía constancia a la tienda registrada;
4. también la envía al cliente cuando el contacto introducido es un correo.

Si el contacto es telefónico, el panel avisa de que la comunicación debe hacerse por ese canal.

## Datos y correo

- `registros/pedidos_comercial.csv`: sin datos personales; uso operativo y de liquidación.
- `registros/pedidos_datos.csv`: cliente y contacto; acceso restringido y depuración periódica.
- `registros/pedidos_eventos.csv`: bitácora de aceptación o rechazo.
- `registros/salida_correo/`: acuses de prueba cuando SMTP no está configurado.

El acuse de tienda se envía al correo del registro maestro, aunque se haya escrito otro en el
formulario. Los fallos de SMTP no duplican pedidos: el registro se conserva y se devuelve un aviso.

Variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `BUZON_PEDIDOS`,
`ADMIN_TOKEN`, `REGISTRO_TIENDAS`, `REGISTRO_EVENTOS`, `REGISTRO_PEDIDOS` y, solo si frontend y
API están separados, `ALLOWED_ORIGINS`.

## Despliegue

Consultar `deploy/README.md`. El backend necesita disco persistente; no debe ejecutarse como una
función efímera de Vercel. Las cabeceras de seguridad se aplican tanto en FastAPI como en los
ejemplos de proxy. Se recomienda un único worker mientras se utilicen CSV.

## Protección de datos

No se aceptan adjuntos. El formulario prohíbe introducir contraseñas, códigos de recuperación,
frases semilla, fotografías del contenido del terminal, categorías especiales o información no
necesaria. `tiendas.csv`, `.env` y todo `registros/` están excluidos de Git.
