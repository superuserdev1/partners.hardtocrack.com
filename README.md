# /pedidos · HardToCrack Partners

Formulario de registro de pedidos para tiendas colaboradoras, con validación por token o PIN,
referencia automática y doble acuse.

## Archivos

- `index.html` — página estática. Sin dependencias externas salvo las fuentes.
- `server.py` — backend FastAPI. Valida, genera referencia, envía acuses y guarda los registros.
- `requirements.txt` — dependencias del backend.

## Configuración del frontend

En `index.html`, constante `API`:

- `""` → el backend vive en el mismo dominio y responde en `/api/pedido`. Recomendado.
- `"https://api.hardtocrack.com"` → backend en otro host.

## Rutas de la tienda

    https://partners.hardtocrack.com/pedidos?t=HTC-MAD-001&k=7f2c9be4

`t` es el código de tienda y `k` su token. Ambos se graban en el QR de la tarjeta metálica
interna de cada tienda. Sin token válido no se registra el pedido. Vía de respaldo: código de
tienda más PIN de cuatro dígitos de la ficha de partner.

## Backend

Espera el registro de tiendas en `../registro/tiendas.csv` (columnas `codigo`, `tienda`,
`email_registrado`, `token`, `pin`, `estado`). Solo valida tiendas en estado `activa`.

    pip install -r requirements.txt
    uvicorn server:app --host 0.0.0.0 --port 8080

Variables de entorno para el envío de correo:

    SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASS SMTP_FROM
    BUZON_PEDIDOS   # por defecto pedidos@hardtocrack.com

Sin `SMTP_HOST`, los acuses se escriben en `registros/salida_correo/` en lugar de enviarse: útil
para pruebas.

## Registros que genera

- `registros/pedidos_comercial.csv` — sin datos personales. Referencia, fecha, código de tienda,
  modelo, pack, precio, estado. Es el registro de trabajo para comisiones.
- `registros/pedidos_datos.csv` — cliente y contacto, solo lo necesario para ejecutar el pedido.

Ninguno de los dos debe subirse al repositorio: están en `.gitignore`, junto con el registro de
tiendas, que contiene tokens y PIN.

## Notas de protección de datos

El acuse a la tienda se envía siempre al correo registrado en su alta, no al que se teclee en el
formulario. El formulario no acepta adjuntos y advierte expresamente de que no se registran
contraseñas, códigos de recuperación ni frases semilla.
