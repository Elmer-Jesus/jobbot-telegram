# JobBot Telegram

Bot gratuito para descubrir ofertas públicas de Computrabajo Perú, analizarlas contra un perfil Backend/Python/Java y enviar las mejores a Telegram con un enlace directo para revisar y postular manualmente.

## Flujo

Computrabajo → filtro y scoring → historial de ofertas vistas → Telegram → revisión manual y postulación

## Stack

- Python
- Requests
- BeautifulSoup
- Telegram Bot API
- GitHub Actions

## Configuración necesaria

En **Settings → Secrets and variables → Actions** crea estos secretos:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Nunca subas el token directamente al repositorio.

## Ejecución

El workflow `Buscar ofertas` puede ejecutarse manualmente desde la pestaña **Actions** con `Run workflow` y también se ejecuta automáticamente varias veces al día.

## Filtros actuales

El bot prioriza ofertas relacionadas con:

- Python
- Java
- Spring Boot
- Flask
- APIs REST
- MySQL / PostgreSQL / SQL
- Git
- Docker
- Linux
- Django
- Web scraping

También reduce la puntuación de cargos claramente senior, Tech Lead o arquitectura.

## Historial

`seen_jobs.json` guarda las URLs ya revisadas para evitar enviar repetidos.
