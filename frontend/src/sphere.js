import * as T from "three";
import { vertex, fragment, pointFragment, wireFragment } from "./shaders";
export class Sphere {
  constructor(host) {
    this.state = "IDLE";
    this.level = 0;
    this.energy = 0;
    this.host = host;
    this.scene = new T.Scene();
    this.camera = new T.PerspectiveCamera(42, 1, 0.1, 100);
    this.camera.position.z = 5.5;
    this.renderer = new T.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "low-power",
    });
    host.append(this.renderer.domElement);
    this.group = new T.Group();
    this.scene.add(this.group);
    this.uniforms = {
      time: { value: 0 },
      audio: { value: 0 },
      intensity: { value: 0 },
      pointSize: { value: 1 },
    };
    this.core = new T.Mesh(
      new T.SphereGeometry(0.92, 64, 48),
      new T.ShaderMaterial({
        vertexShader: vertex,
        fragmentShader: fragment,
        uniforms: this.uniforms,
        transparent: true,
        blending: T.AdditiveBlending,
        depthWrite: false,
      }),
    );
    this.group.add(this.core);
    this.wire = new T.Mesh(
      new T.IcosahedronGeometry(1.04, 3),
      new T.ShaderMaterial({
        vertexShader: vertex,
        fragmentShader: wireFragment,
        uniforms: this.uniforms,
        wireframe: true,
        transparent: true,
        depthWrite: false,
        blending: T.AdditiveBlending,
      }),
    );
    this.group.add(this.wire);
    this.rings = [];
    for (let i = 0; i < 3; i++) {
      let ring = new T.Mesh(
        new T.TorusGeometry(1.3 + i * 0.12, 0.004, 6, 180),
        new T.MeshBasicMaterial({
          color: 0x53dfff,
          transparent: true,
          opacity: 0.5,
        }),
      );
      ring.rotation.set(i * 0.8, 0.5 + i * 0.7, 0);
      this.group.add(ring);
      this.rings.push(ring);
    }
    this.setQuality("MEDIUM");
    new ResizeObserver(() => this.resize()).observe(host);
    this.resize();
    this.last = performance.now();
    this.frames = 0;
    this.frameStart = this.last;
    this.tick = this.tick.bind(this);
    requestAnimationFrame(this.tick);
  }
  setQuality(q) {
    this.quality = q;
    this.renderer.setPixelRatio(
      Math.min(devicePixelRatio, q === "HIGH" ? 1.75 : q === "LOW" ? 1 : 1.4),
    );
    if (this.points) {
      this.group.remove(this.points);
      this.points.geometry.dispose();
      this.points.material.dispose();
    }
    let n = { LOW: 1600, MEDIUM: 3600, HIGH: 6500 }[q],
      p = new Float32Array(n * 3),
      norm = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      let z = 1 - (2 * (i + 0.5)) / n,
        a = i * 2.399963,
        r = Math.sqrt(1 - z * z),
        v = new T.Vector3(r * Math.cos(a), z, r * Math.sin(a));
      norm.set(v.toArray(), i * 3);
      p.set(v.multiplyScalar(i % 15 === 0 ? 1.7 : 1.08).toArray(), i * 3);
    }
    let g = new T.BufferGeometry();
    g.setAttribute("position", new T.BufferAttribute(p, 3));
    g.setAttribute("normal", new T.BufferAttribute(norm, 3));
    this.points = new T.Points(
      g,
      new T.ShaderMaterial({
        vertexShader: vertex,
        fragmentShader: pointFragment,
        uniforms: this.uniforms,
        transparent: true,
        blending: T.AdditiveBlending,
        depthWrite: false,
      }),
    );
    this.group.add(this.points);
  }
  resize() {
    let w = this.host.clientWidth,
      h = this.host.clientHeight;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.position.z = this.camera.aspect < 0.8 ? 7 : 5.5;
    this.camera.updateProjectionMatrix();
  }
  tick(now) {
    requestAnimationFrame(this.tick);
    let dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    let target = {
      IDLE: 0.1,
      LISTENING: 0.7,
      TRANSCRIBING: 0.9,
      THINKING: 1.5,
      SPEAKING: 1.1,
    }[this.state];
    this.energy += (target - this.energy) * (1 - Math.exp(-dt * 4));
    let approximate =
      this.state === "SPEAKING" ? 0.15 + 0.14 * Math.sin(now * 0.009) ** 2 : 0;
    this.uniforms.time.value = now / 1000;
    this.uniforms.audio.value +=
      (Math.max(this.level, approximate) - this.uniforms.audio.value) *
      (1 - Math.exp(-dt * 12));
    this.uniforms.intensity.value = this.energy;
    this.group.rotation.y += dt * (0.09 + this.energy * 0.15);
    this.wire.rotation.x += dt * 0.035;
    this.rings.forEach((r, i) => {
      r.rotation.x += dt * (0.08 + i * 0.03) * (1 + this.energy);
      r.rotation.z += dt * 0.07;
    });
    this.renderer.render(this.scene, this.camera);
    this.frames++;
    if (now - this.frameStart > 1500) {
      let fps = (this.frames * 1000) / (now - this.frameStart);
      document.querySelector("#fps").textContent =
        `${Math.round(fps)} FPS / ${this.quality}`;
      if (fps < 25 && this.quality !== "LOW") this.setQuality("LOW");
      this.frames = 0;
      this.frameStart = now;
    }
  }
}
