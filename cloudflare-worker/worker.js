const OWNER = "Elmer-Jesus";
const REPO = "jobbot-telegram";
const WORKFLOW_FILE = "buscar.yml";
const BRANCH = "main";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "GET") {
      return Response.json({
        ok: true,
        service: "JobBot Telegram webhook",
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const telegramSecret = request.headers.get(
      "X-Telegram-Bot-Api-Secret-Token"
    );

    if (
      !env.TELEGRAM_WEBHOOK_SECRET ||
      telegramSecret !== env.TELEGRAM_WEBHOOK_SECRET
    ) {
      return new Response("Unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad request", { status: 400 });
    }

    ctx.waitUntil(handleUpdate(update, env));
    return new Response("OK");
  },
};

async function handleUpdate(update, env) {
  const message = update?.message;
  if (!message?.text) return;

  const chatId = String(message.chat?.id ?? "");
  if (chatId !== String(env.TELEGRAM_CHAT_ID)) {
    return;
  }

  const command = message.text
    .trim()
    .split(/\s+/)[0]
    .split("@")[0]
    .toLowerCase();

  if (command === "/start" || command === "/ayuda") {
    await sendTelegram(
      env,
      [
        "🤖 <b>JobBot está activo 24/7</b>",
        "",
        "🔎 /buscar - buscar ofertas ahora",
        "📊 /estado - ver el estado de la última búsqueda",
        "❓ /ayuda - mostrar comandos",
        "",
        "Las búsquedas automáticas siguen funcionando aunque tu PC esté apagada.",
      ].join("\n")
    );
    return;
  }

  if (command === "/buscar") {
    const latest = await getLatestWorkflowRun(env);

    if (latest && ["queued", "in_progress"].includes(latest.status)) {
      await sendTelegram(
        env,
        "⏳ Ya hay una búsqueda en curso. Cuando encuentre ofertas compatibles, te llegarán aquí."
      );
      return;
    }

    const dispatched = await dispatchWorkflow(env);

    if (dispatched) {
      await sendTelegram(
        env,
        "🔎 <b>Búsqueda iniciada</b>\n\nGitHub ya está revisando nuevas ofertas. Te mandaré aquí las que superen el filtro de compatibilidad."
      );
    } else {
      await sendTelegram(
        env,
        "⚠️ No pude iniciar la búsqueda en GitHub. Revisa la configuración del token de GitHub en Cloudflare."
      );
    }
    return;
  }

  if (command === "/estado") {
    const latest = await getLatestWorkflowRun(env);

    if (!latest) {
      await sendTelegram(env, "ℹ️ Todavía no encuentro una ejecución del JobBot.");
      return;
    }

    const statusText = formatRunStatus(latest.status, latest.conclusion);
    await sendTelegram(
      env,
      [
        "📊 <b>Estado del JobBot</b>",
        "",
        statusText,
        latest.html_url ? `🔗 <a href=\"${latest.html_url}\">Ver ejecución en GitHub</a>` : "",
      ]
        .filter(Boolean)
        .join("\n")
    );
    return;
  }

  await sendTelegram(
    env,
    "No reconozco ese comando. Usa /buscar, /estado o /ayuda."
  );
}

async function dispatchWorkflow(env) {
  const endpoint = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: githubHeaders(env),
    body: JSON.stringify({ ref: BRANCH }),
  });

  if (!response.ok) {
    console.error("GitHub dispatch error", response.status, await response.text());
    return false;
  }

  return true;
}

async function getLatestWorkflowRun(env) {
  const endpoint = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=1`;

  const response = await fetch(endpoint, {
    headers: githubHeaders(env),
  });

  if (!response.ok) {
    console.error("GitHub runs error", response.status, await response.text());
    return null;
  }

  const data = await response.json();
  return data?.workflow_runs?.[0] ?? null;
}

function githubHeaders(env) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "jobbot-telegram-worker",
  };
}

async function sendTelegram(env, text) {
  const endpoint = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_CHAT_ID,
      text,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });

  if (!response.ok) {
    console.error("Telegram error", response.status, await response.text());
  }
}

function formatRunStatus(status, conclusion) {
  if (status === "queued") {
    return "🕐 La búsqueda está en cola.";
  }

  if (status === "in_progress") {
    return "🔎 La búsqueda está ejecutándose ahora mismo.";
  }

  if (status === "completed") {
    if (conclusion === "success") {
      return "✅ La última búsqueda terminó correctamente.";
    }

    if (conclusion === "failure") {
      return "❌ La última búsqueda terminó con error.";
    }

    if (conclusion === "cancelled") {
      return "🛑 La última búsqueda fue cancelada.";
    }

    return `ℹ️ Última búsqueda finalizada: ${conclusion || "sin resultado"}.`;
  }

  return `ℹ️ Estado actual: ${status || "desconocido"}.`;
}
