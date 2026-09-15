/**
 * Live Drosophila CNS activity viewer.
 * Brain shell: navis-org/navis example neuropil mesh (real fly brain volume).
 * Cells glow from the local MaleCNS LIF simulation.
 */
(function () {
  const HOLD = {};

  function heatColor(t) {
    t = Math.max(0, Math.min(1, t));
    const c = new THREE.Color();
    if (t < 0.25) c.setRGB(0.08, 0.14, 0.28 + t * 0.8);
    else if (t < 0.55) c.setRGB(0.1 + (t - 0.25) * 1.2, 0.45, 0.85);
    else if (t < 0.8) c.setRGB(0.95, 0.55 + (t - 0.55) * 1.2, 0.15);
    else c.setRGB(1, 0.95, 0.75);
    return c;
  }

  function makeLobe(radius, color) {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 24, 18),
      new THREE.MeshPhongMaterial({
        color, transparent: true, opacity: 0.18, emissive: color, emissiveIntensity: 0.2,
      })
    );
    return mesh;
  }

  async function initCnsViewer(el) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07080c);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 20);
    camera.position.set(0.15, -2.15, 1.35);
    camera.lookAt(0, -0.1, 0);

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

    const lobeL = makeLobe(0.42, 0x3ecf8e);
    lobeL.position.set(-0.52, 0.05, 0.12);
    const lobeR = makeLobe(0.42, 0x5b8def);
    lobeR.position.set(0.52, 0.05, 0.12);
    const lobeF = makeLobe(0.28, 0xf5c542);
    lobeF.position.set(0, 0.22, 0.28);
    const vnc = new THREE.Mesh(
      new THREE.CylinderGeometry(0.14, 0.1, 1.05, 16),
      new THREE.MeshPhongMaterial({ color: 0x886644, transparent: true, opacity: 0.22, emissive: 0xffaa33, emissiveIntensity: 0.15 })
    );
    vnc.position.set(0, -0.62, -0.28);
    rig.add(lobeL, lobeR, lobeF, vnc);
    HOLD.lobes = { left: lobeL, right: lobeR, front: lobeF, vnc: vnc };

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
        // neuropil x=LR, y=AP, z=DV → rotate so anterior faces camera
        shell.rotation.x = Math.PI / 2;
        shell.scale.setScalar(0.95);
        rig.add(shell);
        HOLD.shell = shell;
      }
    } catch (err) {
      console.warn("brain mesh load failed", err);
    }

    HOLD.geom = await fetch("/api/geometry").then((r) => r.json());
    const neu = HOLD.geom.neurons || [];
    const positions = new Float32Array(neu.length * 3);
    const colors = new Float32Array(neu.length * 3);
    const sizes = new Float32Array(neu.length);
    neu.forEach((n, i) => {
      positions[i * 3] = n.x;
      positions[i * 3 + 1] = n.y;
      positions[i * 3 + 2] = n.z;
      colors[i * 3] = 0.15; colors[i * 3 + 1] = 0.2; colors[i * 3 + 2] = 0.35;
      sizes[i] = n.role && n.role !== "hidden" ? 14 : 7;
    });
    const pgeo = new THREE.BufferGeometry();
    pgeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    pgeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const pts = new THREE.Points(
      pgeo,
      new THREE.PointsMaterial({
        size: 0.07,
        vertexColors: true,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
    );
    rig.add(pts);
    HOLD.points = pts;
    HOLD.colors = colors;
    HOLD.neurons = neu;

    function resize() {
      const w = el.clientWidth || 360;
      const h = el.clientHeight || 240;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    }
    resize();
    window.addEventListener("resize", resize);

    function tick(t) {
      if (HOLD.rig) HOLD.rig.rotation.y = Math.sin(t * 0.00035) * 0.45;
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    HOLD.ready = true;
  }

  function updateCnsViewer(activity, regions) {
    if (!HOLD.ready || !HOLD.points) return;
    const cols = HOLD.colors;
    const neu = HOLD.neurons;
    let peak = 0.08;
    if (activity && activity.length) {
      for (let i = 0; i < activity.length; i++) peak = Math.max(peak, activity[i] || 0);
    }
    for (let i = 0; i < neu.length; i++) {
      let a = activity && activity[i] != null ? activity[i] : 0;
      const role = neu[i].role || "";
      if (role === "sensor_left") a = Math.max(a, (regions && regions.left) || 0);
      if (role === "sensor_front") a = Math.max(a, (regions && regions.front) || 0);
      if (role === "sensor_right") a = Math.max(a, (regions && regions.right) || 0);
      if (role === "motor_left") a = Math.max(a, (regions && regions.motor_left) || 0);
      if (role === "motor_right") a = Math.max(a, (regions && regions.motor_right) || 0);
      const t = Math.min(1, a / peak);
      const c = heatColor(t);
      cols[i * 3] = c.r;
      cols[i * 3 + 1] = c.g;
      cols[i * 3 + 2] = c.b;
    }
    HOLD.points.geometry.attributes.color.needsUpdate = true;
    HOLD.points.material.size = 0.055 + 0.05 * ((regions && regions.global) || 0);

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
  }

  window.initCnsViewer = initCnsViewer;
  window.updateCnsViewer = updateCnsViewer;
})();
