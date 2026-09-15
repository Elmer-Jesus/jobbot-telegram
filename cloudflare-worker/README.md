# Cloudflare Worker — comandos de Telegram

Este Worker permite controlar JobBot desde Telegram sin depender de una PC encendida.

## Variables / secretos necesarios en Cloudflare

Configura estos cuatro secretos en el Worker:

- `TELEGRAM_BOT_TOKEN` — token actual de BotFather.
- `TELEGRAM_CHAT_ID` — `5816565131`.
- `GITHUB_TOKEN` — fine-grained personal access token con acceso **solo** al repositorio `jobbot-telegram` y permiso **Actions: Read and write**.
- `TELEGRAM_WEBHOOK_SECRET` — una cadena aleatoria que también se usará al registrar el webhook de Telegram.

## Comandos disponibles

- `/start` — muestra el menú.
- `/buscar` — dispara `buscar.yml` en GitHub Actions.
- `/estado` — consulta el estado de la última ejecución.
- `/ayuda` — muestra los comandos.

## Seguridad

El Worker valida el encabezado `X-Telegram-Bot-Api-Secret-Token` y además solo acepta comandos del `TELEGRAM_CHAT_ID` configurado.

No publiques ninguno de los secretos anteriores en el repositorio.

## Registro del webhook

Después de desplegar el Worker y obtener una URL HTTPS, registra el webhook de Telegram usando esa URL y el mismo valor de `TELEGRAM_WEBHOOK_SECRET` como `secret_token`.

Telegram y GitHub tienen documentación oficial para `setWebhook` y `workflow_dispatch` respectivamente.
