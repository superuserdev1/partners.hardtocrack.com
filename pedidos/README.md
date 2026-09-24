# Pedidos de tiendas por correo · fase inicial

La página `/pedidos/` es HTML estático. Prepara un mensaje para
`pedidos@hardtocrack.com` mediante `mailto:`. No hay VPS, API, función de Vercel,
base de datos ni envío automático desde la web. El pedido solo llega cuando la
tienda pulsa **Enviar** en su aplicación de correo. No se genera una referencia de
pedido ni un acuse automático.

## Antes de abrir el canal

1. Configurar `pedidos@hardtocrack.com` como buzón o alias de recepción y enviar
   un mensaje de prueba desde otra cuenta. Comprobar entrega, respuesta y spam.
2. Guardar fuera del repositorio el registro de las primeras cinco referencias
   (`HTC-MAD-001` a `HTC-MAD-005`) y sus códigos alfanuméricos de 12 caracteres.
   En ese registro anotar también el correo autorizado y el estado de cada tienda.
   No subir ese registro al repositorio público.
3. Crear un QR distinto para cada tienda con una URL de este formato:
   `https://partners.hardtocrack.com/pedidos/?t=HTC-MAD-001&k=CODIGO_TIENDA`.
   `t` lleva la referencia y `k` el código de esa tienda. El navegador rellena
   ambos campos; el código aparece en la URL y cualquier persona que escanee
   el QR puede leerlo. Evitar servicios externos de generación o acortamiento
   del enlace para no compartirlo con terceros adicionales.
4. Las cinco filas se crean inicialmente como `SIN_ASIGNAR`: asignar una tienda
   y su remitente antes de admitir pedidos. `HTC-MAD-001` se había usado como
   referencia de prueba; sustituir cualquier token/PIN previo y no aceptar
   pedidos de prueba como reales.

## Tramitación manual

1. El QR rellena referencia y código; la tienda completa el resto de la ficha.
   Si falta uno de los dos, el navegador impide preparar el correo. La web
   coteja el código con la tienda mediante huellas SHA-256 incluidas en la
   página y rechaza un código cambiado o de otra tienda. Esto corrige errores
   de escritura, pero **no autentica a la persona que escanea el QR**.
2. La tienda revisa el borrador y lo envía desde su correo registrado. Si el
   teléfono no tiene una aplicación de correo configurada, copia asunto y texto y
   los pega en su correo habitual.
3. Al llegar el mensaje, comparar **referencia + código + remitente real**
   con el registro privado y confirmar que la tienda esté activa. Una dirección
   escrita en el cuerpo no sustituye esta comparación. Ante discordancia, poner
   el pedido en espera y llamar a un contacto ya registrado.
4. Responder manualmente con acuse y, tras comprobar disponibilidad, precio y
   condiciones, aceptar o rechazar el pedido. Asignar una referencia interna
   correlativa, por ejemplo `HTC-O-260001`, **solo desde la central**. Anotar
   fecha, tienda, estado, precio y respuesta en un registro interno privado.
5. Si hay un uso indebido del QR, suspender la tienda en el registro, generar un
   código nuevo y sustituir el QR impreso.

El código impreso en el QR es visible para quien lo escanee: identifica la
tienda, pero **no autentica a la persona que envía el pedido**. Comprobar el
remitente registrado y, ante dudas, confirmar por un canal ya establecido.
El correo puede ser suplantado y `mailto:` depende del cliente del dispositivo.
No enviar contraseñas, PIN del teléfono, códigos de recuperación, tarjetas,
documentos de identidad ni fotografías. Conservar solo los datos mínimos del
pedido en el buzón y limitar quién puede acceder a él.

## Código anterior

Los archivos `server.py`, `admin.html`, `tiendas.py` y los ejemplos de servidor
pertenecen al prototipo con backend. La página estática no los llama. No publicar
el panel de administración del prototipo ni usar sus antiguos PIN/tokens para
validar esta fase manual.
