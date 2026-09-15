/**
 * Live Drosophila CNS activity viewer.
 * Brain shell: navis-org/navis example neuropil mesh (real fly brain volume).
 * Cells glow from the local MaleCNS LIF simulation.
 * Click a lobe, chip, or cell to inspect live region activity; drag / +/− to orbit and zoom.
 */
(function () {
  const HOLD = {};

  const REGIONS = {
    left: {
      title: "Antennal lobe L",
      role: "Left ultrasonic → sensory",
      keys: ["left"],
      mesh: "left",
      neuronRoles: ["sensor_left"],
    },
    front: {
      title: "Antennal lobe C",
      role: "Front ultrasonic → sensory",
      keys: ["front"],
      mesh: "front",
      neuronRoles: ["sensor_front"],
    },
    right: {
      title: "Antennal lobe R",
      role: "Right ultrasonic → sensory",
      keys: ["right"],
      mesh: "right",
      neuronRoles: ["sensor_right"],
    },
    vnc: {
      title: "Ventral nerve cord",
      role: "Descending motor drive",
      keys: ["motor_left", "motor_right"],
      mesh: "vnc",
      neuronRoles: ["motor_left", "motor_right"],
    },
    global: {
      title: "Whole CNS",
      role: "Mean MaleCNS LIF activity",
      keys: ["global"],
      mesh: null,
      neuronRoles: null,
    },
  };

  function heatColor(t) {
    t = Math.max(0, Math.min(1, t));
    const c = new THREE.Color();
    if (t < 0.25) c.setRGB(0.08, 0.14, 0.28 + t * 0.8);
    else if (t < 0.55) c.setRGB(0.1 + (t - 0.25) * 1.2, 0.45, 0.85);
    else if (t < 0.8) c.setRGB(0.95, 0.55 + (t - 0.55) * 1.2, 0.15);
    else c.setRGB(1, 0.95, 0.75);
    return c;
  }

  function pct(v) {
    return Math.round(Math.max(0, Math.min(1, v || 0)) * 100) + "%";
  }

  function regionFromRole(role) {
    if (role === "sensor_left") return "left";
    if (role === "sensor_front") return "front";
    if (role === "sensor_right") return "right";
    if (role === "motor_left" || role === "motor_right") return "vnc";
    return "global";
  }

  function makeLobe(radius, color) {
    return new THREE.Mesh(
      new THREE.SphereGeometry(radius, 24, 18),
      new THREE.MeshPhongMaterial({
        color, transparent: true, opacity: 0.18, emissive: color, emissiveIntensity: 0.2,
      })
    );
  }

  function makeHitSphere(radius, userData) {
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 16, 12),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.userData = userData;
    return hit;
  }

  async function initCnsViewer(el) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07080c);
    const camera = new THREE.PerspectiveCamera(40, 1, 0.02, 40);
    camera.position.set(0, -3.2, 0.9);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xfff1d0, 1.0);
    key.position.set(1.5, -2, 2.5);
    scene.add(key);
    scene.add(new THREE.PointLight(0x5ce1c5, 0.6, 8));

    const rig = new THREE.Group();
    scene.add(rig);
    HOLD.rig = rig;

    const content = new THREE.Group();
    rig.add(content);

    const lobeL = makeLobe(0.16, 0x3ecf8e);
    lobeL.position.set(-0.42, 0.04, 0.08);
    const lobeR = makeLobe(0.16, 0x5b8def);
    lobeR.position.set(0.42, 0.04, 0.08);
    const lobeF = makeLobe(0.11, 0xf5c542);
    lobeF.position.set(0, 0.16, 0.18);
    const vnc = new THREE.Mesh(
      new THREE.CylinderGeometry(0.07, 0.05, 0.55, 16),
      new THREE.MeshPhongMaterial({ color: 0x886644, transparent: true, opacity: 0.22, emissive: 0xffaa33, emissiveIntensity: 0.15 })
    );
    vnc.position.set(0, -0.42, -0.18);
    content.add(lobeL, lobeR, lobeF, vnc);
    HOLD.lobes = { left: lobeL, right: lobeR, front: lobeF, vnc: vnc };

    const pickables = [];
    function addHit(mesh, region, radius) {
      const hit = makeHitSphere(radius, { region });
      hit.position.copy(mesh.position);
      content.add(hit);
      pickables.push(hit);
    }
    addHit(lobeL, "left", 0.24);
    addHit(lobeR, "right", 0.24);
    addHit(lobeF, "front", 0.18);
    const vncHit = new THREE.Mesh(
      new THREE.CylinderGeometry(0.14, 0.12, 0.62, 12),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    vncHit.position.copy(vnc.position);
    vncHit.userData = { region: "vnc" };
    content.add(vncHit);
    pickables.push(vncHit);
    HOLD.pickables = pickables;

    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(1, 22, 16),
      new THREE.MeshBasicMaterial({ color: 0xf5c542, wireframe: true, transparent: true, opacity: 0.55 })
    );
    halo.visible = false;
    content.add(halo);
    HOLD.halo = halo;

    try {
      const meshJson = await fetch("/api/brain-mesh").then((r) => r.json());
      if (meshJson.vertices && meshJson.faces) {
        const geo = new THREE.BufferGeometry();
        const verts = new Float32Array(meshJson.vertices.flat());
        geo.setAttribute("position", new THREE.BufferAttribute(verts, 3));
        geo.setIndex(meshJson.faces.flat());
        geo.computeVertexNormals();
        const shell = new THREE.Mesh(
          geo,
          new THREE.MeshPhongMaterial({
            color: 0x6fa8c9,
            transparent: true,
            opacity: 0.22,
            shininess: 40,
            side: THREE.DoubleSide,
            emissive: 0x123040,
            emissiveIntensity: 0.35,
          })
        );
        shell.rotation.x = Math.PI / 2;
        shell.scale.setScalar(0.72);
        shell.raycast = function () {};
        content.add(shell);
        HOLD.shell = shell;
      }
    } catch (err) {
      console.warn("brain mesh load failed", err);
    }

    HOLD.geom = await fetch("/api/geometry").then((r) => r.json());
    const neu = HOLD.geom.neurons || [];
    const positions = new Float32Array(neu.length * 3);
    const colors = new Float32Array(neu.length * 3);
    neu.forEach((n, i) => {
      positions[i * 3] = n.x;
      positions[i * 3 + 1] = n.y;
      positions[i * 3 + 2] = n.z;
      colors[i * 3] = 0.15; colors[i * 3 + 1] = 0.2; colors[i * 3 + 2] = 0.35;
    });
    const pgeo = new THREE.BufferGeometry();
    pgeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    pgeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const pts = new THREE.Points(
      pgeo,
      new THREE.PointsMaterial({
        size: 0.035,
        vertexColors: true,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
    );
    content.add(pts);
    HOLD.points = pts;
    HOLD.colors = colors;
    HOLD.neurons = neu;
    HOLD.content = content;
    HOLD.el = el;
    HOLD.camera = camera;
    HOLD.renderer = renderer;
    HOLD.scene = scene;

    HOLD.orbit = {
      yaw: 0,
      pitch: 0.18,
      radius: 3.2,
      baseRadius: 3.2,
      auto: false,
      min: 0.55,
      max: 8,
    };
    HOLD.viewCenter = new THREE.Vector3();
    HOLD.brainCenter = new THREE.Vector3();
    HOLD.selected = { kind: "region", id: "global" };
    HOLD.lastRegions = {};
    HOLD.lastActivity = [];

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: 0.06 };
    const pointer = new THREE.Vector2();
    const canvas = renderer.domElement;

    function setPointer(ev) {
      const r = canvas.getBoundingClientRect();
      pointer.x = ((ev.clientX - r.left) / Math.max(1, r.width)) * 2 - 1;
      pointer.y = -((ev.clientY - r.top) / Math.max(1, r.height)) * 2 + 1;
    }

    function applyCamera() {
      const c = HOLD.viewCenter;
      const o = HOLD.orbit;
      o.radius = Math.max(o.min, Math.min(o.max, o.radius));
      o.pitch = Math.max(-1.15, Math.min(1.15, o.pitch));
      const r = o.radius;
      const cp = Math.cos(o.pitch);
      camera.position.set(
        c.x + r * Math.sin(o.yaw) * cp,
        c.y - r * Math.cos(o.yaw) * cp,
        c.z + r * Math.sin(o.pitch)
      );
      camera.near = Math.max(0.02, r / 40);
      camera.far = Math.max(20, r * 12);
      camera.lookAt(c);
      camera.updateProjectionMatrix();
    }

    function fitView() {
      const target = HOLD.content || rig;
      target.updateWorldMatrix(true, true);
      const box = new THREE.Box3().setFromObject(target);
      if (box.isEmpty()) {
        applyCamera();
        return;
      }
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      HOLD.brainCenter.copy(center);
      HOLD.viewCenter.copy(center);
      const vFov = (camera.fov * Math.PI) / 180;
      const fitH = size.z * 0.55 + size.y * 0.55;
      const fitW = size.x * 0.55;
      const distH = fitH / Math.max(0.001, Math.tan(vFov / 2));
      const distW = fitW / Math.max(0.001, Math.tan(vFov / 2) * camera.aspect);
      const dist = Math.max(distH, distW, 0.8) * 1.25;
      HOLD.orbit.baseRadius = dist;
      HOLD.orbit.radius = dist;
      HOLD.orbit.yaw = 0;
      HOLD.orbit.pitch = 0.18;
      HOLD.orbit.max = Math.max(8, dist * 2.4);
      applyCamera();
    }

    function resize() {
      const w = Math.max(1, el.clientWidth || 360);
      const h = Math.max(1, el.clientHeight || 240);
      camera.aspect = w / h;
      renderer.setSize(w, h, false);
      if (!HOLD.framed) {
        fitView();
        HOLD.framed = true;
      } else {
        applyCamera();
      }
    }

    function zoomBy(factor) {
      HOLD.orbit.radius *= factor;
      applyCamera();
    }

    function setHalo(mesh, isVnc) {
      if (!mesh) {
        halo.visible = false;
        return;
      }
      halo.visible = true;
      halo.position.copy(mesh.position);
      if (isVnc) {
        halo.scale.set(0.2, 0.38, 0.2);
      } else {
        const r = (mesh.geometry.parameters && mesh.geometry.parameters.radius) || 0.16;
        halo.scale.setScalar(r * 1.45);
      }
    }

    function focusRegion(id, zoomIn) {
      HOLD.selected = { kind: "region", id: id || "global" };
      const meta = REGIONS[HOLD.selected.id] || REGIONS.global;
      const mesh = meta.mesh && HOLD.lobes ? HOLD.lobes[meta.mesh] : null;
      setHalo(mesh, meta.mesh === "vnc");
      if (zoomIn && mesh) {
        mesh.getWorldPosition(HOLD.viewCenter);
        HOLD.orbit.radius = Math.max(HOLD.orbit.min, HOLD.orbit.baseRadius * 0.48);
      } else if (id === "global") {
        HOLD.viewCenter.copy(HOLD.brainCenter);
        HOLD.orbit.radius = HOLD.orbit.baseRadius;
      }
      applyCamera();
      syncChips();
      refreshInspect();
    }

    function selectCell(neuron) {
      HOLD.selected = { kind: "cell", neuron, id: regionFromRole(neuron.role) };
      const mesh = HOLD.lobes && HOLD.lobes[REGIONS[HOLD.selected.id].mesh];
      setHalo(mesh, HOLD.selected.id === "vnc");
      HOLD.viewCenter.set(neuron.x, neuron.y, neuron.z);
      HOLD.orbit.radius = Math.max(HOLD.orbit.min, HOLD.orbit.baseRadius * 0.42);
      applyCamera();
      syncChips();
      refreshInspect();
    }

    function pick(ev) {
      setPointer(ev);
      raycaster.setFromCamera(pointer, camera);
      const lobeHits = raycaster.intersectObjects(HOLD.pickables, false);
      if (lobeHits.length) {
        focusRegion(lobeHits[0].object.userData.region, true);
        return;
      }
      const cellHits = raycaster.intersectObject(HOLD.points, false);
      if (cellHits.length && cellHits[0].index != null) {
        const n = HOLD.neurons[cellHits[0].index];
        if (n) {
          selectCell(n);
          return;
        }
      }
      focusRegion("global", false);
    }

    function hover(ev) {
      if (drag.active) return;
      setPointer(ev);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(HOLD.pickables, false).length
        || raycaster.intersectObject(HOLD.points, false).length;
      canvas.classList.toggle("is-hit", !!hit);
    }

    function refreshInspect() {
      const title = document.getElementById("cns-card-title");
      const roleEl = document.getElementById("cns-card-role");
      const actEl = document.getElementById("cns-card-act");
      const nEl = document.getElementById("cns-card-n");
      const extra = document.getElementById("cns-card-extra");
      if (!title) return;
      const regions = HOLD.lastRegions || {};
      const sel = HOLD.selected || { kind: "region", id: "global" };

      if (sel.kind === "cell" && sel.neuron) {
        const n = sel.neuron;
        const a = HOLD.lastActivity[n.index];
        title.textContent = "Cell " + n.body_id;
        roleEl.textContent = (n.region || "CNS") + " · " + (n.role || "hidden");
        actEl.textContent = a == null ? "—" : pct(a);
        nEl.textContent = "1";
        extra.textContent = "Region " + (REGIONS[sel.id] ? REGIONS[sel.id].title : sel.id);
        return;
      }

      const meta = REGIONS[sel.id] || REGIONS.global;
      title.textContent = meta.title;
      roleEl.textContent = meta.role;
      if (sel.id === "vnc") {
        actEl.textContent = pct(Math.max(regions.motor_left || 0, regions.motor_right || 0));
        extra.textContent = "Motor L " + pct(regions.motor_left) + " · Motor R " + pct(regions.motor_right);
      } else {
        actEl.textContent = pct(regions[meta.keys[0]]);
        extra.textContent = "";
      }
      if (meta.neuronRoles) {
        nEl.textContent = String(HOLD.neurons.filter((n) => meta.neuronRoles.includes(n.role)).length);
      } else {
        nEl.textContent = String(HOLD.neurons.length);
      }
    }

    function syncChips() {
      const id = HOLD.selected && HOLD.selected.id;
      document.querySelectorAll("#cns-chips [data-region]").forEach((b) => {
        b.classList.toggle("active", b.dataset.region === id);
      });
    }

    function updateChipPcts(regions) {
      const map = {
        left: regions.left,
        front: regions.front,
        right: regions.right,
        vnc: Math.max(regions.motor_left || 0, regions.motor_right || 0),
        global: regions.global,
      };
      document.querySelectorAll("#cns-chips [data-pct]").forEach((el) => {
        el.textContent = pct(map[el.dataset.pct]);
      });
    }

    HOLD.focusRegion = focusRegion;
    HOLD.refreshInspect = refreshInspect;
    HOLD.updateChipPcts = updateChipPcts;
    HOLD.applyCamera = applyCamera;
    HOLD.fitView = fitView;
    HOLD.zoomBy = zoomBy;

    const drag = { active: false, moved: false, x: 0, y: 0 };
    canvas.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      drag.active = true;
      drag.moved = false;
      drag.x = ev.clientX;
      drag.y = ev.clientY;
      HOLD.orbit.auto = false;
      setSpinBtn();
      canvas.classList.add("is-drag");
      canvas.setPointerCapture(ev.pointerId);
    });
    canvas.addEventListener("pointermove", (ev) => {
      if (!drag.active) {
        hover(ev);
        return;
      }
      const dx = ev.clientX - drag.x;
      const dy = ev.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      HOLD.orbit.yaw -= dx * 0.008;
      HOLD.orbit.pitch += dy * 0.006;
      drag.x = ev.clientX;
      drag.y = ev.clientY;
      applyCamera();
    });
    function endDrag(ev) {
      if (!drag.active) return;
      drag.active = false;
      canvas.classList.remove("is-drag");
      try { canvas.releasePointerCapture(ev.pointerId); } catch (e) { /* already released */ }
      if (!drag.moved) pick(ev);
    }
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);
    canvas.addEventListener("dblclick", (ev) => {
      ev.preventDefault();
      pick(ev);
    });
    canvas.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const factor = ev.deltaY > 0 ? 1.12 : 0.89;
      zoomBy(factor);
    }, { passive: false });

    const btnIn = document.getElementById("cns-in");
    const btnOut = document.getElementById("cns-out");
    const btnFit = document.getElementById("cns-fit");
    const btnSpin = document.getElementById("cns-spin");
    function setSpinBtn() {
      if (btnSpin) btnSpin.classList.toggle("active", !!HOLD.orbit.auto);
    }
    if (btnIn) btnIn.addEventListener("click", () => zoomBy(0.78));
    if (btnOut) btnOut.addEventListener("click", () => zoomBy(1.28));
    if (btnFit) btnFit.addEventListener("click", () => {
      HOLD.orbit.auto = false;
      setSpinBtn();
      fitView();
      focusRegion("global", false);
    });
    if (btnSpin) btnSpin.addEventListener("click", () => {
      HOLD.orbit.auto = !HOLD.orbit.auto;
      setSpinBtn();
    });
    document.querySelectorAll("#cns-chips [data-region]").forEach((b) => {
      b.addEventListener("click", () => focusRegion(b.dataset.region, b.dataset.region !== "global"));
    });

    resize();
    window.addEventListener("resize", resize);
    requestAnimationFrame(resize);
    focusRegion("global", false);

    function tick(t) {
      if (HOLD.orbit.auto && !drag.active) {
        HOLD.orbit.yaw += 0.004;
        applyCamera();
      }
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    HOLD.ready = true;
  }

  function updateCnsViewer(activity, regions) {
    if (!HOLD.ready || !HOLD.points) return;
    HOLD.lastRegions = regions || {};
    HOLD.lastActivity = activity || [];
    const cols = HOLD.colors;
    const neu = HOLD.neurons;
    let peak = 0.08;
    if (activity && activity.length) {
      for (let i = 0; i < activity.length; i++) peak = Math.max(peak, activity[i] || 0);
    }
    const sel = HOLD.selected;
    for (let i = 0; i < neu.length; i++) {
      let a = activity && activity[i] != null ? activity[i] : 0;
      const role = neu[i].role || "";
      if (role === "sensor_left") a = Math.max(a, (regions && regions.left) || 0);
      if (role === "sensor_front") a = Math.max(a, (regions && regions.front) || 0);
      if (role === "sensor_right") a = Math.max(a, (regions && regions.right) || 0);
      if (role === "motor_left") a = Math.max(a, (regions && regions.motor_left) || 0);
      if (role === "motor_right") a = Math.max(a, (regions && regions.motor_right) || 0);
      let t = Math.min(1, a / peak);
      if (sel && sel.kind === "region" && sel.id && sel.id !== "global") {
        const meta = REGIONS[sel.id];
        if (meta && meta.neuronRoles && !meta.neuronRoles.includes(role)) t *= 0.28;
      }
      const c = heatColor(t);
      cols[i * 3] = c.r;
      cols[i * 3 + 1] = c.g;
      cols[i * 3 + 2] = c.b;
    }
    HOLD.points.geometry.attributes.color.needsUpdate = true;
    HOLD.points.material.size = 0.028 + 0.02 * ((regions && regions.global) || 0);

    const L = HOLD.lobes;
    if (L) {
      L.left.material.emissiveIntensity = 0.15 + 2.4 * ((regions && regions.left) || 0);
      L.left.material.opacity = 0.14 + 0.45 * ((regions && regions.left) || 0);
      L.right.material.emissiveIntensity = 0.15 + 2.4 * ((regions && regions.right) || 0);
      L.right.material.opacity = 0.14 + 0.45 * ((regions && regions.right) || 0);
      L.front.material.emissiveIntensity = 0.15 + 2.4 * ((regions && regions.front) || 0);
      L.front.material.opacity = 0.14 + 0.5 * ((regions && regions.front) || 0);
      const m = Math.max((regions && regions.motor_left) || 0, (regions && regions.motor_right) || 0);
      L.vnc.material.emissiveIntensity = 0.12 + 2.2 * m;
      L.vnc.material.opacity = 0.16 + 0.4 * m;
    }
    if (HOLD.shell && regions) {
      const g = regions.global || 0;
      HOLD.shell.material.emissiveIntensity = 0.25 + 1.4 * g;
      HOLD.shell.material.opacity = 0.18 + 0.2 * g;
    }
    if (HOLD.updateChipPcts) HOLD.updateChipPcts(HOLD.lastRegions);
    if (HOLD.refreshInspect) HOLD.refreshInspect();
  }

  window.initCnsViewer = initCnsViewer;
  window.updateCnsViewer = updateCnsViewer;
})();
