import "./style.css";
import { Sphere } from "./sphere";
import { Voice } from "./audio";
import { refreshWeb, webState, finishWeb, renderSources } from "./web";
const $ = (s) => document.querySelector(s);
let sphere;
try {
  sphere = new Sphere($("#canvas"));
} catch {
  $("#error").textContent =
    "WebGL을 사용할 수 없습니다. Chrome 하드웨어 가속을 확인하세요. 텍스트 대화는 사용 가능합니다.";
}
let sid,
  settings,
  health,
  busy = false,
  aborter,
  timer,
  greeted = false;
const state = (s) => {
  if (sphere) sphere.state = s;
  $("#state").textContent = {
    IDLE: "SYSTEM READY",
    LISTENING: "LISTENING",
    TRANSCRIBING: "PROCESSING VOICE",
    THINKING: "PROCESSING",
    SPEAKING: "J.A.R.V.I.S. SPEAKING",
    SEARCHING: "SEARCHING WEB",
  }[s];
};
const error = (e) => ($("#error").textContent = e.message || String(e));
const voice = new Voice((level) => {
  if (sphere) sphere.level = level;
});
async function api(path, options = {}) {
  let r = await fetch("/api" + path, options);
  if (!r.ok) {
    let j = await r.json().catch(() => ({ detail: r.statusText }));
    throw Error(j.detail);
  }
  return r.json();
}
const json = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
function message(role, text) {
  let div = document.createElement("div");
  div.className = "message " + role;
  let small = document.createElement("small");
  small.textContent = role === "user" ? "YOU" : "J.A.R.V.I.S.";
  let content = document.createElement("span");
  content.textContent = text;
  div.append(small, content);
  $("#messages").append(div);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return content;
}
function controls() {
  for (let id of ["new", "delete", "clear", "memory"])
    $("#" + id).disabled = busy || voice.recording;
  $("#mic").disabled = busy || voice.speaking;
  $("#input").disabled = busy || voice.recording;
  for (let b of $("#sessions").children) b.disabled = busy || voice.recording;
}
async function sessions() {
  let items = await api("/sessions");
  $("#sessions").replaceChildren();
  for (let s of items) {
    let b = document.createElement("button");
    b.textContent = (s.id === sid ? "› " : "") + s.title;
    b.title = s.created;
    b.disabled = busy || voice.recording;
    b.onclick = () => load(s.id).catch(error);
    $("#sessions").append(b);
  }
}
async function load(id) {
  voice.stopSpeaking();
  sid = id;
  $("#messages").replaceChildren();
  for (let m of await api("/sessions/" + sid)) {
    const output = message(m.role, m.content);
    renderSources(output, m.sources);
  }
  await sessions();
}
async function fresh() {
  let s = await api("/sessions", { method: "POST" });
  await load(s.id);
}
async function refresh() {
  refreshWeb().catch(() => webState("OFFLINE", "검색 연결 상태 확인 실패"));
  health = await api("/health");
  $("#health").textContent =
    `SERVER • ONLINE\nOLLAMA • ${health.ollama ? "ONLINE" : "OFFLINE"}\nMODEL • ${settings.model}\nINSTALLED • ${health.selected_installed ? "YES" : "NO"}\nSTT • ${health.stt.loaded ? health.stt.device : "미로딩"}\nGPU • ${health.gpu || "조회 불가"}\nMIC • ${navigator.mediaDevices ? "권한 요청 대기" : "사용 불가"}\nTTS • ${voice.voices.length ? "LOCAL KO" : "오프라인 음성 없음"}`;
  if (health.error) error(health.error);
  else if (!health.selected_installed)
    error(
      "선택한 모델이 설치되어 있지 않습니다. README의 ollama pull 명령을 확인하세요.",
    );
  else $("#error").textContent = "";
  if (health.gpu) {
    let free = Number(health.gpu.split(",")[2]);
    if (free < 2000)
      error(
        "GPU 여유 메모리가 2GB 미만입니다. 작은 모델 또는 CPU STT를 사용하세요.",
      );
  }
  if (health.selected_installed && !greeted && voice.voices.length) {
    greeted = true;
    speak("자비스 시스템이 준비되었습니다. 무엇을 도와드릴까요?");
  }
}
function speak(text) {
  if (!voice.voices.length && $("#tts").checked)
    error(
      "오프라인 한국어 음성이 없습니다. Windows 한국어 음성 팩을 설치하세요. 텍스트 답변은 정상 제공됩니다.",
    );
  voice.speak(
    text,
    () => {
      state("SPEAKING");
      controls();
    },
    () => {
      state("IDLE");
      controls();
    },
  );
  controls();
}
async function send(text) {
  if (busy || voice.recording || !text.trim()) return;
  voice.stopSpeaking();
  busy = true;
  controls();
  aborter = new AbortController();
  state("THINKING");
  $("#error").textContent = "";
  message("user", text);
  let output = message("assistant", ""),
    answer = "",
    complete = false;
  try {
    let r = await fetch(`/api/sessions/${sid}/chat`, {
      ...json("POST", { text }),
      signal: aborter.signal,
    });
    if (!r.ok) throw Error((await r.json()).detail);
    let reader = r.body.getReader(),
      decoder = new TextDecoder(),
      buffer = "";
    while (true) {
      let part = await reader.read();
      buffer += decoder.decode(part.value || new Uint8Array(), {
        stream: !part.done,
      });
      let lines = buffer.split("\n");
      buffer = lines.pop();
      for (let line of lines) {
        if (!line) continue;
        let e = JSON.parse(line);
        if (e.error) throw Error(e.error);
        if (["SEARCHING", "THINKING"].includes(e.state)) state(e.state);
        if (e.web) webState(e.web);
        if (e.sources || e.warnings)
          renderSources(output, e.sources, e.warnings);
        if (e.token) {
          answer += e.token;
          output.textContent = answer;
          $("#messages").scrollTop = $("#messages").scrollHeight;
        }
        if (e.done) complete = true;
      }
      if (part.done) break;
    }
    if (!complete) throw Error("응답 연결이 종료되었습니다. 다시 시도하세요.");
  } catch (e) {
    if (e.name !== "AbortError") error(e);
    output.textContent = answer
      ? answer + "\n[미완료 · 저장되지 않음]"
      : "[응답 없음]";
  } finally {
    busy = false;
    finishWeb();
    state("IDLE");
    controls();
    await sessions();
    if (complete && answer) speak(answer);
  }
}
$("#form").onsubmit = (e) => {
  e.preventDefault();
  let text = $("#input").value;
  $("#input").value = "";
  send(text);
};
$("#cancel").onclick = () => {
  aborter?.abort();
  voice.stopSpeaking();
};
async function record() {
  try {
    if (voice.recording) {
      clearTimeout(timer);
      let blob = await voice.stop();
      $("#mic").textContent = "● 마이크";
      busy = true;
      controls();
      state("TRANSCRIBING");
      let data = new FormData();
      data.append("file", blob, "voice.webm");
      try {
        let result = await api("/stt", { method: "POST", body: data });
        busy = false;
        await send(result.text);
      } finally {
        busy = false;
        if (!voice.speaking) state("IDLE");
        controls();
        await refresh();
      }
    } else {
      if (busy) return;
      busy = true;
      controls();
      await voice.start();
      busy = false;
      state("LISTENING");
      $("#mic").textContent = "■ 녹음 종료";
      controls();
      timer = setTimeout(record, 60000);
    }
  } catch (e) {
    error(
      e.name === "NotAllowedError"
        ? "마이크 권한이 거부되었습니다. Chrome 사이트 권한을 확인하세요."
        : e,
    );
    busy = false;
    state("IDLE");
    controls();
  }
}
$("#mic").onclick = record;
$("#new").onclick = () => fresh().catch(error);
$("#refresh").onclick = () => refresh().catch(error);
$("#delete").onclick = async () => {
  if (confirm("현재 대화를 삭제할까요?"))
    try {
      await api("/sessions/" + sid, { method: "DELETE" });
      await fresh();
    } catch (e) {
      error(e);
    }
};
$("#clear").onclick = async () => {
  if (confirm("모든 대화를 영구 삭제할까요?"))
    try {
      await api("/sessions", { method: "DELETE" });
      await fresh();
    } catch (e) {
      error(e);
    }
};
$("#memory").onclick = async () => {
  let all = await api("/sessions"),
    current = all.find((s) => s.id === sid);
  let text = prompt(
    "최근 24개 메시지 밖의 중요한 내용을 요약하세요. 다음 요청에 함께 전달됩니다.",
    current?.memory || "",
  );
  if (text !== null)
    api(`/sessions/${sid}/memory`, json("PUT", { text })).catch(error);
};
$("#settings").onclick = async () => {
  try {
    await refresh();
    for (let key of [
      "temperature",
      "stt_model",
      "quality",
      "personality",
      "particle_size",
      "web_provider",
      "searxng_url",
    ])
      $("#" + key).value = settings[key];
    $("#web_enabled").checked = settings.web_enabled;
    $("#web_fetch_pages").checked = settings.web_fetch_pages;
    $("#model").replaceChildren(
      ...[...new Set([settings.model, ...health.models])].map(
        (m) => new Option(m, m),
      ),
    );
    $("#model").value = settings.model;
    voice.refresh();
    $("#dialog").showModal();
  } catch (e) {
    error(e);
  }
};
$("#config").onsubmit = async (e) => {
  e.preventDefault();
  try {
    let next = {};
    for (let key of [
      "model",
      "stt_model",
      "quality",
      "personality",
      "particle_size",
      "web_provider",
      "searxng_url",
    ])
      next[key] = $("#" + key).value;
    next.web_enabled = $("#web_enabled").checked;
    next.web_fetch_pages = $("#web_fetch_pages").checked;
    if (!next.web_enabled && $("#state").textContent === "SEARCHING WEB")
      aborter?.abort();
    next.temperature = Number($("#temperature").value);
    settings = await api("/settings", json("PUT", next));
    sphere?.setQuality(settings.quality);
    if (sphere) sphere.uniforms.pointSize.value = settings.particle_size || 1;
    $("#dialog").close();
    await refresh();
  } catch (e) {
    error(e);
  }
};
$("#close").onclick = () => $("#dialog").close();
$("#web-check").onclick = async () => {
  $("#web-check").disabled = true;
  try {
    await refreshWeb(true);
  } catch (e) {
    error(e);
  } finally {
    $("#web-check").disabled = false;
  }
};
$("#fullscreen").onclick = () => {
  (document.fullscreenElement
    ? document.exitFullscreen()
    : document.documentElement.requestFullscreen()
  ).catch(error);
};
$("#tts").onchange = () => {
  if (!$("#tts").checked) voice.stopSpeaking();
  localStorage.setItem("jarvis.tts", $("#tts").checked);
};
$("#tts").checked = localStorage.getItem("jarvis.tts") !== "false";
$("#volume").value = localStorage.getItem("jarvis.volume") || ".8";
$("#volume").onchange = () =>
  localStorage.setItem("jarvis.volume", $("#volume").value);
setInterval(
  () => ($("#clock").textContent = new Date().toLocaleString("ko-KR")),
  1000,
);
(async () => {
  try {
    settings = await api("/settings");
    sphere?.setQuality(settings.quality);
    if (sphere) sphere.uniforms.pointSize.value = settings.particle_size || 1;
    let all = await api("/sessions");
    if (all.length) await load(all[0].id);
    else await fresh();
    await refresh();
    setInterval(() => {
      if (!busy && !voice.recording) refresh().catch(error);
    }, 15000);
  } catch (e) {
    error(e);
  }
})();

$("#voice").onchange = () =>
  localStorage.setItem(
    "jarvis.voice",
    $("#voice").selectedOptions[0]?.textContent || "",
  );
$("#rate").value = localStorage.getItem("jarvis.rate") || "1";
$("#rate").onchange = () =>
  localStorage.setItem("jarvis.rate", $("#rate").value);
