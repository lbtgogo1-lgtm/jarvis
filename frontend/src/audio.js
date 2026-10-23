export class Voice {
  constructor(onLevel) {
    this.onLevel = onLevel;
    this.recording = false;
    this.speaking = false;
    this.voices = [];
    this.refresh();
    window.speechSynthesis?.addEventListener("voiceschanged", () =>
      this.refresh(),
    );
  }
  refresh() {
    this.voices =
      window.speechSynthesis
        ?.getVoices()
        .filter((v) => v.lang.startsWith("ko") && v.localService) || [];
    let select = document.querySelector("#voice");
    let previous =
      select.selectedOptions[0]?.textContent ||
      localStorage.getItem("jarvis.voice");
    select.replaceChildren(...this.voices.map((v, i) => new Option(v.name, i)));
    let previousIndex = this.voices.findIndex((v) => v.name === previous);
    if (previousIndex >= 0) select.value = previousIndex;
    if (!this.voices.length)
      select.add(new Option("오프라인 한국어 음성 없음", ""));
  }
  async start() {
    this.stopSpeaking();
    if (!navigator.mediaDevices?.getUserMedia)
      throw Error(
        "마이크를 사용할 수 없습니다. Chrome의 localhost에서 실행하세요.",
      );
    let stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    try {
      this.context = new AudioContext();
      await this.context.resume();
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 512;
      this.context.createMediaStreamSource(stream).connect(this.analyser);
      this.samples = new Uint8Array(512);
      this.freq = new Uint8Array(256);
      this.stream = stream;
      this.chunks = [];
      this.recorder = new MediaRecorder(stream);
      this.result = new Promise((resolve) => {
        this.recorder.onstop = () =>
          resolve(new Blob(this.chunks, { type: this.recorder.mimeType }));
      });
      this.recorder.ondataavailable = (e) => this.chunks.push(e.data);
      this.recorder.start();
      this.recording = true;
      this.meter();
    } catch (e) {
      stream.getTracks().forEach((t) => t.stop());
      throw e;
    }
  }
  meter() {
    if (!this.recording) return;
    this.analyser.getByteTimeDomainData(this.samples);
    this.analyser.getByteFrequencyData(this.freq);
    let rms = Math.sqrt(
      this.samples.reduce((a, v) => a + ((v - 128) / 128) ** 2, 0) /
        this.samples.length,
    );
    let bass = this.freq.slice(0, 40).reduce((a, v) => a + v, 0) / (40 * 255);
    this.onLevel(Math.min(1, rms * 4 + bass * 0.2));
    this.raf = requestAnimationFrame(() => this.meter());
  }
  async stop() {
    if (!this.recording) return;
    this.recording = false;
    cancelAnimationFrame(this.raf);
    this.recorder.stop();
    this.stream.getTracks().forEach((t) => t.stop());
    await this.context.close();
    this.onLevel(0);
    return this.result;
  }
  stopSpeaking() {
    window.speechSynthesis?.cancel();
    this.speaking = false;
    this.onEnd?.();
  }
  speak(text, onStart, onEnd) {
    this.refresh();
    if (
      !document.querySelector("#tts").checked ||
      !this.voices.length ||
      this.recording
    ) {
      onEnd();
      return false;
    }
    let u = new SpeechSynthesisUtterance(text);
    u.voice = this.voices[Number(document.querySelector("#voice").value) || 0];
    u.lang = "ko-KR";
    u.volume = Number(document.querySelector("#volume").value);
    u.rate = Number(document.querySelector("#rate").value) || 1;
    this.onEnd = onEnd;
    u.onstart = () => {
      this.speaking = true;
      onStart();
    };
    u.onend = u.onerror = () => {
      this.speaking = false;
      onEnd();
    };
    this.speaking = true;
    speechSynthesis.speak(u);
    return true;
  }
}
