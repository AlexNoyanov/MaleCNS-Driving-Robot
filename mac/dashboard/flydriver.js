/**
 * Live 3D fruit-fly driver on the 2WD acrylic chassis.
 * Forward: looks ahead, presses gas. Reverse: looks back. Turns: steers.
 */
(function () {
  const HOLD = {};

  function mat(color, extra) {
    return new THREE.MeshStandardMaterial(Object.assign({
      color, roughness: 0.55, metalness: 0.08,
    }, extra || {}));
  }

  function wheel() {
    const g = new THREE.Group();
    const tire = new THREE.Mesh(
      new THREE.TorusGeometry(0.28, 0.08, 12, 24),
      mat(0x1a1a1a, { roughness: 0.9 })
    );
    tire.rotation.y = Math.PI / 2;
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.12, 12), mat(0xf5c400));
    hub.rotation.z = Math.PI / 2;
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.14, 8), mat(0xe6b800));
    cap.rotation.z = Math.PI / 2;
    g.add(tire, hub, cap);
    return g;
  }

  function makeChassis() {
    const g = new THREE.Group();
    const deck = new THREE.Mesh(
      new THREE.BoxGeometry(1.55, 0.05, 2.35),
      new THREE.MeshPhongMaterial({
        color: 0xc5d4e0, transparent: true, opacity: 0.45, shininess: 90,
      })
    );
    deck.position.y = 0.32;
    g.add(deck);

    const batt = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.28, 1.05), mat(0x151515));
    batt.position.set(0, 0.48, -0.05);
    g.add(batt);
    const sw = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.06, 0.22), mat(0x222222));
    sw.position.set(0.22, 0.64, 0.28);
    g.add(sw);

    // +Z is forward: yellow drive wheels at the nose, small caster at the tail.
    const caster = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 12), mat(0xc0c4ca, { metalness: 0.7, roughness: 0.25 }));
    caster.position.set(0, 0.1, -0.92);
    g.add(caster);
    const fork = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.22, 8), mat(0xb8bcc2, { metalness: 0.6 }));
    fork.position.set(0, 0.22, -0.92);
    g.add(fork);

    const motorL = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.18, 0.42), mat(0xf0c000));
    motorL.position.set(-0.58, 0.22, 0.72);
    const motorR = motorL.clone();
    motorR.position.x = 0.58;
    g.add(motorL, motorR);

    const wL = wheel();
    wL.position.set(-0.78, 0.28, 0.72);
    const wR = wheel();
    wR.position.set(0.78, 0.28, 0.72);
    g.add(wL, wR);
    HOLD.wheels = [wL, wR];

    const col = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.42, 10), mat(0x333333));
    col.position.set(0, 0.72, 0.55);
    g.add(col);
    const steer = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.018, 8, 20), mat(0x222222));
    steer.position.set(0, 0.94, 0.55);
    steer.rotation.x = Math.PI / 2.4;
    g.add(steer);
    HOLD.steer = steer;

    const pedal = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.02, 0.16), mat(0xc0392b));
    pedal.position.set(0.22, 0.64, 0.55);
    g.add(pedal);
    HOLD.pedal = pedal;

    return g;
  }

  function makeFly() {
    const fly = new THREE.Group();
    const tan = mat(0xb8860b);
    const dark = mat(0x5c3b0a);

    const thorax = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 12), tan);
    thorax.scale.set(1, 0.85, 1.15);
    thorax.position.set(0, 0.18, 0.02);
    fly.add(thorax);

    const abdomen = new THREE.Mesh(new THREE.SphereGeometry(0.14, 16, 12), dark);
    abdomen.scale.set(0.85, 0.75, 1.55);
    abdomen.position.set(0, 0.14, -0.22);
    fly.add(abdomen);

    const head = new THREE.Group();
    head.position.set(0, 0.22, 0.18);
    const skull = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), tan);
    head.add(skull);
    const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 10), mat(0xc0392b, { roughness: 0.3, metalness: 0.2 }));
    eyeL.position.set(-0.08, 0.02, 0.06);
    const eyeR = eyeL.clone();
    eyeR.position.x = 0.08;
    head.add(eyeL, eyeR);
    const antL = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.12, 6), dark);
    antL.position.set(-0.04, 0.12, 0.04);
    antL.rotation.z = 0.4;
    const antR = antL.clone();
    antR.position.x = 0.04;
    antR.rotation.z = -0.4;
    head.add(antL, antR);
    fly.add(head);
    HOLD.head = head;

    const wingGeo = new THREE.PlaneGeometry(0.42, 0.18);
    const wingMat = new THREE.MeshPhongMaterial({
      color: 0xcfe8ff, transparent: true, opacity: 0.35, side: THREE.DoubleSide,
    });
    const wingL = new THREE.Mesh(wingGeo, wingMat);
    wingL.position.set(-0.22, 0.28, -0.02);
    wingL.rotation.set(-0.5, 0.5, 0.35);
    const wingR = wingL.clone();
    wingR.position.x = 0.22;
    wingR.rotation.y = -0.5;
    wingR.rotation.z = -0.35;
    fly.add(wingL, wingR);
    HOLD.wings = [wingL, wingR];

    function leg(x, z, rot) {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.22, 6), dark);
      m.position.set(x, 0.02, z);
      m.rotation.z = rot;
      fly.add(m);
      return m;
    }
    HOLD.gasLeg = leg(0.12, 0.12, -0.9);
    leg(-0.12, 0.12, 0.9);
    leg(0.14, -0.02, -0.5);
    leg(-0.14, -0.02, 0.5);
    leg(0.1, -0.16, -0.35);
    leg(-0.1, -0.16, 0.35);

    fly.position.set(0, 0.72, -0.02);
    HOLD.fly = fly;
    return fly;
  }

  const CM_SCALE = 0.05;
  const NET_COLS = 19;
  const NET_ROWS = 6;
  const WALL_H = 1.55;

  function cmToScene(cm) {
    if (cm == null || cm < 0) return 6.2;
    return Math.max(0.55, Math.min(120, Number(cm)) * CM_SCALE);
  }

  function makeRangeNet() {
    const group = new THREE.Group();
    const nVerts = NET_COLS * NET_ROWS;
    const positions = new Float32Array(nVerts * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const idx = [];
    for (let r = 0; r < NET_ROWS; r++) {
      for (let c = 0; c < NET_COLS - 1; c++) {
        const a = r * NET_COLS + c;
        idx.push(a, a + 1);
      }
    }
    for (let c = 0; c < NET_COLS; c++) {
      for (let r = 0; r < NET_ROWS - 1; r++) {
        const a = r * NET_COLS + c;
        idx.push(a, a + NET_COLS);
      }
    }
    geo.setIndex(idx);
    const lines = new THREE.LineSegments(
      geo,
      new THREE.LineBasicMaterial({ color: 0x5ce1c5, transparent: true, opacity: 0.8 })
    );
    group.add(lines);

    const fillGeo = new THREE.PlaneGeometry(1, 1, 12, 4);
    const fillMat = new THREE.MeshBasicMaterial({
      color: 0x5ce1c5, transparent: true, opacity: 0.08, side: THREE.DoubleSide,
    });
    const frontFill = new THREE.Mesh(fillGeo.clone(), fillMat.clone());
    const leftFill = new THREE.Mesh(fillGeo.clone(), fillMat.clone());
    const rightFill = new THREE.Mesh(fillGeo.clone(), fillMat.clone());
    leftFill.rotation.y = Math.PI / 2;
    rightFill.rotation.y = Math.PI / 2;
    group.add(frontFill, leftFill, rightFill);

    const rayMat = new THREE.LineBasicMaterial({ color: 0xf5c542, transparent: true, opacity: 0.55 });
    function ray() {
      const g = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0.35, 0),
        new THREE.Vector3(0, 0.35, 1),
      ]);
      return new THREE.Line(g, rayMat);
    }
    const rayF = ray();
    const rayL = ray();
    const rayR = ray();
    group.add(rayF, rayL, rayR);

    HOLD.net = {
      group, geo, positions, lines,
      frontFill, leftFill, rightFill,
      rayF, rayL, rayR,
    };
    layoutRangeNet(4, 4, 4);
    return group;
  }

  function layoutRangeNet(leftU, frontU, rightU) {
    if (!HOLD.net) return;
    const pos = HOLD.net.positions;
    for (let c = 0; c < NET_COLS; c++) {
      const t = c / (NET_COLS - 1);
      const ang = -Math.PI / 2 + t * Math.PI;
      let d;
      if (t < 0.5) d = leftU + (frontU - leftU) * (t * 2);
      else d = frontU + (rightU - frontU) * ((t - 0.5) * 2);
      const x = Math.sin(ang) * d;
      const z = Math.cos(ang) * d;
      for (let r = 0; r < NET_ROWS; r++) {
        const y = 0.02 + WALL_H * (r / (NET_ROWS - 1));
        const i = (r * NET_COLS + c) * 3;
        pos[i] = x;
        pos[i + 1] = y;
        pos[i + 2] = z;
      }
    }
    HOLD.net.geo.attributes.position.needsUpdate = true;
    HOLD.net.geo.computeBoundingSphere();

    const widthF = Math.max(1.2, (leftU + rightU) * 0.55);
    HOLD.net.frontFill.position.set(0, WALL_H / 2, frontU);
    HOLD.net.frontFill.scale.set(widthF, WALL_H, 1);
    HOLD.net.leftFill.position.set(-leftU, WALL_H / 2, 0);
    HOLD.net.leftFill.scale.set(Math.max(1.2, frontU * 0.9), WALL_H, 1);
    HOLD.net.rightFill.position.set(rightU, WALL_H / 2, 0);
    HOLD.net.rightFill.scale.set(Math.max(1.2, frontU * 0.9), WALL_H, 1);

    const near = Math.min(leftU, frontU, rightU);
    const heat = Math.max(0, Math.min(1, (3.2 - near) / 3.2));
    const color = new THREE.Color().setHSL(0.48 - heat * 0.48, 0.75, 0.55);
    HOLD.net.lines.material.color.copy(color);
    HOLD.net.frontFill.material.color.copy(color);
    HOLD.net.leftFill.material.color.copy(color);
    HOLD.net.rightFill.material.color.copy(color);
    const fade = near > 5.4 ? 0.22 : 0.82;
    HOLD.net.lines.material.opacity = fade;

    function setRay(line, x, z) {
      const p = line.geometry.attributes.position.array;
      p[0] = 0; p[1] = 0.38; p[2] = 0.2;
      p[3] = x; p[4] = 0.7; p[5] = z;
      line.geometry.attributes.position.needsUpdate = true;
    }
    setRay(HOLD.net.rayF, 0, frontU);
    setRay(HOLD.net.rayL, -leftU, 0);
    setRay(HOLD.net.rayR, rightU, 0);
  }

  function initFlyDriver(el) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07080c);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 40);
    camera.position.set(3.6, 2.4, 4.4);
    camera.lookAt(0, 0.45, 0.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    const key = new THREE.DirectionalLight(0xfff6e0, 1.35);
    key.position.set(3, 6, 4);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xa8c4e8, 0.55);
    fill.position.set(-4, 2, -2);
    scene.add(fill);
    const rim = new THREE.PointLight(0xf5c542, 0.55, 8);
    rim.position.set(0, 1.4, 0.4);
    scene.add(rim);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(10, 48),
      mat(0x2a3140, { roughness: 1 })
    );
    floor.rotation.x = -Math.PI / 2;
    scene.add(floor);
    const groundNet = new THREE.GridHelper(12, 24, 0x4a5d72, 0x243040);
    groundNet.position.y = 0.015;
    scene.add(groundNet);

    const rig = new THREE.Group();
    rig.add(makeChassis());
    rig.add(makeFly());
    scene.add(rig);
    HOLD.rig = rig;
    scene.add(makeRangeNet());

    HOLD.drive = 0;
    HOLD.turn = 0;
    HOLD.spin = 0;
    HOLD.look = 0;
    HOLD.gas = 0;
    HOLD.steerAng = 0;
    HOLD.wallL = 4;
    HOLD.wallF = 4;
    HOLD.wallR = 4;
    HOLD.tgtL = 4;
    HOLD.tgtF = 4;
    HOLD.tgtR = 4;

    function resize() {
      const w = el.clientWidth || 400;
      const h = el.clientHeight || 280;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    }
    resize();
    window.addEventListener("resize", resize);

    function tick(t) {
      const dt = 0.016;
      HOLD.steerAng += (HOLD.turn * 0.7 - HOLD.steerAng) * 0.12;
      HOLD.look += (((HOLD.drive < -40) ? 1 : 0) - HOLD.look) * 0.1;
      HOLD.gas += ((HOLD.drive > 25 ? Math.min(1, HOLD.drive / 180) : 0) - HOLD.gas) * 0.14;
      HOLD.spin += (HOLD.drive / 255) * 0.25;

      if (HOLD.steer) HOLD.steer.rotation.y = HOLD.steerAng;
      if (HOLD.head) {
        HOLD.head.rotation.y = HOLD.look * 2.6;
        HOLD.head.rotation.x = HOLD.look * 0.15;
      }
      if (HOLD.fly) {
        HOLD.fly.rotation.y = HOLD.look * 0.85;
        HOLD.fly.rotation.z = -HOLD.steerAng * 0.25;
        HOLD.fly.position.z = -0.02 - HOLD.look * 0.06;
      }
      if (HOLD.pedal) HOLD.pedal.rotation.x = HOLD.gas * 0.7;
      if (HOLD.gasLeg) HOLD.gasLeg.rotation.x = HOLD.gas * 0.5;
      if (HOLD.wings) {
        const flap = Math.sin(t * 0.02) * 0.08 * (0.3 + HOLD.gas);
        HOLD.wings[0].rotation.z = 0.35 + flap;
        HOLD.wings[1].rotation.z = -0.35 - flap;
      }
      if (HOLD.wheels) {
        HOLD.wheels.forEach((w) => { w.rotation.x = HOLD.spin; });
      }
      HOLD.wallL += (HOLD.tgtL - HOLD.wallL) * 0.12;
      HOLD.wallF += (HOLD.tgtF - HOLD.wallF) * 0.12;
      HOLD.wallR += (HOLD.tgtR - HOLD.wallR) * 0.12;
      layoutRangeNet(HOLD.wallL, HOLD.wallF, HOLD.wallR);

      if (HOLD.rig) {
        HOLD.rig.rotation.y = Math.sin(t * 0.00025) * 0.12;
      }
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    HOLD.ready = true;
  }

  function updateFlyDriver(leftPwm, rightPwm, leftCm, frontCm, rightCm) {
    const l = Number(leftPwm) || 0;
    const r = Number(rightPwm) || 0;
    HOLD.drive = 0.5 * (l + r);
    HOLD.turn = (l - r) / 255;
    HOLD.tgtL = cmToScene(leftCm);
    HOLD.tgtF = cmToScene(frontCm);
    HOLD.tgtR = cmToScene(rightCm);
    const caption = document.getElementById("pilot-caption");
    if (!caption) return;
    const fmt = (cm) => (cm == null || cm < 0 ? "miss" : Math.round(cm) + " cm");
    let pose = "Idle";
    if (HOLD.drive < -40) pose = "Looking back · reverse";
    else if (HOLD.drive > 25) pose = "Eyes forward · gas down";
    else if (Math.abs(HOLD.turn) > 0.15) pose = HOLD.turn > 0 ? "Steering right" : "Steering left";
    caption.textContent = pose + " · net L " + fmt(leftCm) + " / F " + fmt(frontCm) + " / R " + fmt(rightCm);
  }

  window.initFlyDriver = initFlyDriver;
  window.updateFlyDriver = updateFlyDriver;
})();
