import json
import os
import re
import time
from html import escape
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://pe.computrabajo.com"
SEEN_FILE = Path("seen_jobs.json")

SEARCH_URLS = [
    f"{BASE_URL}/trabajo-de-desarrollador-backend-python",
    f"{BASE_URL}/trabajo-de-java-spring-boot",
    f"{BASE_URL}/trabajo-de-python-flask",
    f"{BASE_URL}/trabajo-de-desarrollador-backend",
]

PROFILE_KEYWORDS = {
    "python": 18,
    "java": 16,
    "spring boot": 16,
    "flask": 14,
    "api rest": 14,
    "rest api": 14,
    "mysql": 10,
    "postgresql": 8,
    "sql": 8,
    "git": 5,
    "docker": 6,
    "linux": 5,
    "django": 7,
    "json": 4,
    "web scraping": 6,
    "beautifulsoup": 4,
    "requests": 4,
}

TITLE_BOOSTS = {
    "backend": 18,
    "python": 14,
    "java": 14,
    "desarrollador": 8,
    "developer": 8,
    "automatizacion": 8,
    "automation": 8,
}

TITLE_PENALTIES = {
    "senior": 18,
    "sr.": 18,
    "sr ": 18,
    "tech lead": 25,
    "lider tecnico": 25,
    "líder técnico": 25,
    "arquitecto": 25,
    "architect": 25,
}

MIN_SCORE = int(os.getenv("JOBBOT_MIN_SCORE", "50"))
MAX_LINKS_PER_SEARCH = int(os.getenv("JOBBOT_MAX_LINKS_PER_SEARCH", "15"))
MAX_TELEGRAM_RESULTS = int(os.getenv("JOBBOT_MAX_TELEGRAM_RESULTS", "8"))
FORCE_SHOW = os.getenv("JOBBOT_FORCE_SHOW", "0").strip() == "1"
NOTIFY_SUMMARY = os.getenv("JOBBOT_NOTIFY_SUMMARY", "0").strip() == "1"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.7",
    }
)


def clean(text: str) -> str:
    return " ".join((text or "").split())


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except Exception:
        return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fetch_html(url: str) -> str:
    response = SESSION.get(url, timeout=25)
    response.raise_for_status()
    return response.text


def collect_job_links(search_url: str) -> list[str]:
    soup = BeautifulSoup(fetch_html(search_url), "html.parser")
    links = []
    local_seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "")
        if "/ofertas-de-trabajo/oferta-de-trabajo-de-" not in href:
            continue

        url = urljoin(BASE_URL, href).split("#", 1)[0]
        if url in local_seen:
            continue

        local_seen.add(url)
        links.append(url)

        if len(links) >= MAX_LINKS_PER_SEARCH:
            break

    return links


def extract_salary(text: str) -> str:
    for pattern in (
        r"S/\.\s*[\d\.,]+\s*\(Mensual\)",
        r"S/\.\s*[\d\.,]+\s*-\s*S/\.\s*[\d\.,]+",
        r"S/\.\s*[\d\.,]+",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean(match.group(0))
    return ""


def parse_job(url: str) -> dict | None:
    soup = BeautifulSoup(fetch_html(url), "html.parser")
    main = soup.find("main") or soup
    h1 = main.find("h1")
    if not h1:
        return None

    title = clean(h1.get_text(" ", strip=True))
    company = "Empresa no indicada"
    location = "Ubicación no indicada"

    company_p = h1.find_next("p")
    if company_p:
        line = clean(company_p.get_text(" ", strip=True))
        if " - " in line:
            company, location = [clean(x) for x in line.rsplit(" - ", 1)]
        elif line:
            company = line

    description = clean(main.get_text(" ", strip=True))

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary": extract_salary(description),
        "description": description,
        "url": url,
    }


def score_job(job: dict) -> tuple[int, list[str], list[str]]:
    title = job["title"].lower()
    text = f"{job['title']} {job['description']}".lower()

    matched = []
    points = 0
    total = sum(PROFILE_KEYWORDS.values())

    for keyword, weight in PROFILE_KEYWORDS.items():
        if keyword in text:
            matched.append(keyword)
            points += weight

    score = round((points / total) * 72)

    for keyword, boost in TITLE_BOOSTS.items():
        if keyword in title:
            score += boost

    for keyword, penalty in TITLE_PENALTIES.items():
        if keyword in title:
            score -= penalty

    score = max(0, min(100, score))

    missing_core = [
        keyword
        for keyword in ("python", "java", "spring boot", "flask", "api rest", "mysql")
        if keyword not in text
    ]

    return score, matched, missing_core


def telegram_request(payload: dict) -> None:
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en GitHub Secrets")

    endpoint = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    response = requests.post(endpoint, json=payload, timeout=20)
    response.raise_for_status()


def send_text(text: str) -> None:
    telegram_request(
        {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
    )


def send_job(job: dict, score: int, matched: list[str], missing: list[str]) -> None:
    matched_text = ", ".join(matched[:8]) or "Coincidencia por título/perfil"
    missing_text = ", ".join(missing[:4]) or "Sin faltantes principales detectados"

    text = (
        f"💼 <b>{escape(job['title'])}</b>\n"
        f"🏢 {escape(job['company'])}\n"
        f"📍 {escape(job['location'])}\n"
        f"💰 {escape(job['salary'] or 'No indicado')}\n\n"
        f"🎯 <b>Compatibilidad: {score}%</b>\n"
        f"✅ Coincide: {escape(matched_text)}\n"
        f"⚠️ Faltantes: {escape(missing_text)}\n\n"
        "🔎 Revísala y postula tú mismo desde el enlace."
    )

    telegram_request(
        {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🔗 Ver y postular", "url": job["url"]}]
                ]
            },
        }
    )


def main() -> None:
    seen = load_seen()
    candidates = []
    all_links = []
    unique_links = set()
    source_errors = 0

    print(f"Modo manual/forzado: {FORCE_SHOW}")

    for search_url in SEARCH_URLS:
        try:
            links = collect_job_links(search_url)
            print(f"{search_url}: {len(links)} ofertas encontradas")
        except Exception as exc:
            source_errors += 1
            print(f"Error buscando {search_url}: {exc}")
            continue

        for link in links:
            if link not in unique_links:
                unique_links.add(link)
                all_links.append(link)

    for url in all_links:
        if not FORCE_SHOW and url in seen:
            continue

        try:
            job = parse_job(url)
            if not job:
                continue
            score, matched, missing = score_job(job)
            candidates.append((score, job, matched, missing))
        except Exception as exc:
            print(f"Error leyendo {url}: {exc}")

    candidates.sort(key=lambda item: item[0], reverse=True)

    sent = 0
    compatible = 0

    for score, job, matched, missing in candidates:
        if score < MIN_SCORE:
            seen.add(job["url"])
            print(f"{score}% | omitida | {job['title']}")
            continue

        compatible += 1

        if sent >= MAX_TELEGRAM_RESULTS:
            # No la marcamos como vista para que una ejecución automática futura
            # todavía pueda enviarla si no fue mostrada.
            continue

        try:
            send_job(job, score, matched, missing)
            seen.add(job["url"])
            sent += 1
            print(f"{score}% | enviada | {job['title']}")
            time.sleep(0.7)
        except Exception as exc:
            print(f"Error enviando Telegram: {exc}")

    save_seen(seen)

    print(
        f"Listo. URLs: {len(all_links)} | Analizadas: {len(candidates)} | "
        f"Compatibles: {compatible} | Enviadas: {sent}"
    )

    if NOTIFY_SUMMARY:
        if not all_links:
            send_text(
                "⚠️ <b>Búsqueda terminada</b>\n\n"
                "No pude extraer ofertas de Computrabajo en esta ejecución. "
                f"Fuentes con error: {source_errors}."
            )
        elif sent > 0:
            send_text(
                "✅ <b>Búsqueda terminada</b>\n\n"
                f"Revisé {len(candidates)} ofertas y te envié {sent} "
                f"con compatibilidad de {MIN_SCORE}% o más."
            )
        else:
            send_text(
                "✅ <b>Búsqueda terminada</b>\n\n"
                f"Revisé {len(candidates)} ofertas, pero ninguna superó "
                f"el filtro de {MIN_SCORE}% en esta ejecución."
            )


if __name__ == "__main__":
    main()
