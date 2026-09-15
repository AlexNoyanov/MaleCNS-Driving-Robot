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

  function initFlyDriver(el) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07080c);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 40);
    camera.position.set(2.4, 1.7, 2.6);
    camera.lookAt(0, 0.5, 0);

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
      new THREE.CircleGeometry(4, 32),
      mat(0x2a3140, { roughness: 1 })
    );
    floor.rotation.x = -Math.PI / 2;
    scene.add(floor);

    const rig = new THREE.Group();
    rig.add(makeChassis());
    rig.add(makeFly());
    scene.add(rig);
    HOLD.rig = rig;

    HOLD.drive = 0;
    HOLD.turn = 0;
    HOLD.spin = 0;
    HOLD.look = 0;
    HOLD.gas = 0;
    HOLD.steerAng = 0;

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
      if (HOLD.rig) {
        HOLD.rig.rotation.y = Math.sin(t * 0.00025) * 0.15;
      }
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    HOLD.ready = true;
  }

  function updateFlyDriver(leftPwm, rightPwm) {
    const l = Number(leftPwm) || 0;
    const r = Number(rightPwm) || 0;
    HOLD.drive = 0.5 * (l + r);
    HOLD.turn = (l - r) / 255;
    const caption = document.getElementById("pilot-caption");
    if (!caption) return;
    if (HOLD.drive < -40) caption.textContent = "Looking back · reverse";
    else if (HOLD.drive > 25) caption.textContent = "Eyes forward · gas down";
    else if (Math.abs(HOLD.turn) > 0.15) caption.textContent = HOLD.turn > 0 ? "Steering right" : "Steering left";
    else caption.textContent = "Idle · waiting for drive";
  }

  window.initFlyDriver = initFlyDriver;
  window.updateFlyDriver = updateFlyDriver;
})();
