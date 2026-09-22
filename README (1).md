# Despliegue recomendado

Este proyecto guarda CSV y acuses en disco local. Por ello el backend necesita un servidor con
almacenamiento persistente (VPS con Nginx o Caddy). **Vercel no es adecuado para el backend**:
su sistema de archivos de ejecución no es persistente. Puede alojar una copia estática del
frontend, pero no debe procesar ni conservar pedidos.

## Antes de publicar

1. Crear el usuario de servicio y copiar el proyecto a `/opt/hardtocrack-pedidos`.
2. Crear un entorno virtual e instalar `requirements.txt`.
3. Copiar `.env.example` a `/etc/hardtocrack-pedidos.env`, permisos `600`.
4. Generar `ADMIN_TOKEN` con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
5. Crear `pedidos@hardtocrack.com` y configurar SMTP. Puede reenviar a `partners@`.
6. Dar de alta las tiendas reales con `registro/tiendas.py`.
7. Revocar la prueba antes de producción:
   `python registro/tiendas.py revocar HTC-MAD-001 --estado suspendida --motivo "Fin de pruebas"`.
8. Instalar la unidad `hardtocrack-pedidos.service` y una de las configuraciones de proxy.
9. Confirmar HTTPS y probar `/api/salud`, `/pedidos/` y `/pedidos/admin`.

Se fija `--workers 1` porque el almacenamiento CSV se coordina dentro del proceso. Para crecer a
varios procesos o servidores, migrar los registros a PostgreSQL antes de aumentar workers.
