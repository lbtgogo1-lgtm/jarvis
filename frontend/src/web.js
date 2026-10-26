const badge = () => document.querySelector("#web-status");
let searching = false;
let lastLabel = "OFFLINE";
export function webState(label, detail = "") {
  searching = label === "SEARCHING WEB";
  if (!searching) lastLabel = label;
  badge().textContent = label;
  badge().title = detail;
  badge().dataset.online = String(label === "WEB CONNECTED");
}
export function finishWeb() {
  if (searching) webState(lastLabel);
}
export async function refreshWeb(force = false) {
  const response = await fetch("/api/web/" + (force ? "check" : "status"), {
    method: force ? "POST" : "GET",
  });
  if (!response.ok) throw Error("인터넷 검색 상태를 확인할 수 없습니다.");
  const status = await response.json();
  if (!searching)
    webState(status.connected ? "WEB CONNECTED" : "OFFLINE", status.message);
  document.querySelector("#web-help").textContent = status.message;
  return status;
}
function line(parent, value, className = "") {
  const p = document.createElement("p");
  p.textContent = value;
  p.className = className;
  parent.append(p);
  return p;
}
function weatherCard(parent, weather) {
  const current = weather.current || {},
    units = weather.current_units || {};
  const format = (key) =>
    current[key] == null ? "미확인" : `${current[key]} ${units[key] || ""}`;
  line(
    parent,
    `${weather.location} · 기온 ${format("temperature_2m")} · 강수 ${format("precipitation")} · 풍속 ${format("wind_speed_10m")}`,
  );
  const daily = weather.daily || {},
    du = weather.daily_units || {};
  (daily.time || []).slice(0, 3).forEach((date, i) => {
    const value = (key) =>
      daily[key]?.[i] == null ? "미확인" : `${daily[key][i]} ${du[key] || ""}`;
    line(
      parent,
      `${date} 예보 · ${value("temperature_2m_min")} ~ ${value("temperature_2m_max")} · 강수 ${value("precipitation_sum")} · 최대 풍속 ${value("wind_speed_10m_max")}`,
    );
  });
  line(
    parent,
    weather.time_basis || "Open-Meteo 모델 기반 날씨",
    "source-meta",
  );
}
export function renderSources(output, sources = [], warnings = []) {
  const message = output.parentElement;
  message.querySelector(".sources")?.remove();
  if (!sources.length && !warnings.length) return;
  const container = document.createElement("div");
  container.className = "sources";
  warnings.forEach((warning) => line(container, warning, "source-warning"));
  if (sources.length)
    line(
      container,
      "답변에 제공된 출처 · 발행일과 사건 날짜는 다를 수 있습니다.",
      "source-meta",
    );
  for (const source of sources) {
    let url;
    try {
      url = new URL(source.url);
    } catch {
      continue;
    }
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      continue;
    const card = document.createElement("section");
    card.className = "source-card";
    const link = document.createElement("a");
    link.textContent = `[${source.id}] ${source.title || url.hostname}`;
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    card.append(link);
    line(
      card,
      `발행일: ${source.published_at || "미확인"} · 사건일: ${source.event_date || "미확인"}`,
      "source-meta",
    );
    if (source.observed_at)
      line(
        card,
        `날씨 기준 시각: ${source.observed_at} (${source.timezone || "시간대 미확인"})`,
        "source-meta",
      );
    line(
      card,
      `조회: ${source.retrieved_at || "미확인"} · ${source.provider || url.hostname}`,
      "source-meta",
    );
    if (source.weather) weatherCard(card, source.weather);
    else if (source.summary) {
      const details = document.createElement("details"),
        label = document.createElement("summary");
      label.textContent =
        source.kind === "page" ? "읽은 원문 발췌" : "검색 요약";
      details.append(label);
      line(details, source.summary);
      card.append(details);
    }
    container.append(card);
  }
  message.append(container);
}
