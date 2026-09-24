# Pedidos de tiendas por correo · fase inicial

La página `/pedidos/` es HTML estático. Prepara un mensaje para
`pedidos@hardtocrack.com` mediante `mailto:`. No hay VPS, API, función de Vercel,
base de datos ni envío automático desde la web. El pedido solo llega cuando la
tienda pulsa **Enviar** en su aplicación de correo. No se genera una referencia de
pedido ni un acuse automático.

## Antes de abrir el canal

1. Configurar `pedidos@hardtocrack.com` como buzón o alias de recepción y enviar
   un mensaje de prueba desde otra cuenta. Comprobar entrega, respuesta y spam.
2. Guardar fuera del repositorio el registro privado de las primeras cinco
   referencias (`HTC-MAD-001` a `HTC-MAD-005`) y sus respectivos códigos de
   12 caracteres. Ningún código debe figurar en un QR, enlace, JavaScript ni
   documento público. En el registro privado anotar también el correo autorizado
   y el estado de cada tienda.
3. Entregar cada código solo a la tienda correspondiente. Las cinco filas se
   crean inicialmente como `SIN_ASIGNAR`: asignar una tienda y su remitente antes
   de admitir pedidos. `HTC-MAD-001` se había usado como referencia de prueba;
   sustituir cualquier token/PIN previo y no aceptar pedidos de prueba como reales.
4. El QR puede llevar solo la referencia pública, por ejemplo
   `https://partners.hardtocrack.com/pedidos/?t=HTC-MAD-001`. También se aceptan
   los parámetros públicos `partner` y `ref`; nunca pasar el código privado en URL.

## Tramitación manual

1. La tienda rellena la ficha y el código privado. Si falta uno de los dos,
   el navegador impide preparar el correo. La web comprueba el formato del código,
   pero **no puede comprobar su autenticidad**.
2. La tienda revisa el borrador y lo envía desde su correo registrado. Si el
   teléfono no tiene una aplicación de correo configurada, copia asunto y texto y
   los pega en su correo habitual.
3. Al llegar el mensaje, comparar **referencia + código privado + remitente real**
   con el registro privado y confirmar que la tienda esté activa. Una dirección
   escrita en el cuerpo no sustituye esta comparación. Ante discordancia, poner
   el pedido en espera y llamar a un contacto ya registrado.
4. Responder manualmente con acuse y, tras comprobar disponibilidad, precio y
   condiciones, aceptar o rechazar el pedido. Asignar una referencia interna
   correlativa, por ejemplo `HTC-O-260001`, **solo desde la central**. Anotar
   fecha, tienda, estado, precio y respuesta en un registro interno privado.
5. Si un código se divulga, suspender la tienda en el registro, generar uno nuevo
   con un generador criptográfico y entregarlo por un canal verificado.

El código compartido más el remitente registrado son un control manual básico;
el correo puede ser suplantado y `mailto:` depende del cliente del dispositivo.
No enviar contraseñas, PIN del teléfono, códigos de recuperación, tarjetas,
documentos de identidad ni fotografías. Conservar solo los datos mínimos del
pedido en el buzón y limitar quién puede acceder a él.

## Código anterior

Los archivos `server.py`, `admin.html`, `tiendas.py` y los ejemplos de servidor
pertenecen al prototipo con backend. La página estática no los llama. No publicar
el panel de administración del prototipo ni usar sus antiguos PIN/tokens para
validar esta fase manual.
