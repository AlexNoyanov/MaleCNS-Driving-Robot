/**
 * Compound-eye view of the robot camera.
 * Samples the live frame through two hexagonal ommatidia mosaics
 * with Drosophila-like (red-poor, UV/green-rich) spectral weighting.
 */
(function () {
  function flyShift(r, g, b) {
    const uv = Math.max(0, b - r * 0.55) + Math.abs(g - r) * 0.18;
    const nr = r * 0.16 + g * 0.26 + uv * 0.72;
    const ng = r * 0.2 + g * 0.78 + b * 0.28;
    const nb = r * 0.06 + g * 0.34 + b * 0.95 + uv * 0.28;
    const punch = (v) => Math.max(0, Math.min(255, (v - 118) * 1.28 + 128));
    return [punch(nr), punch(ng), punch(nb)];
  }

  function hexPath(ctx, x, y, r) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 6 + i * (Math.PI / 3);
      const px = x + r * Math.cos(a);
      const py = y + r * Math.sin(a);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
  }

  function initFlyEye(canvas) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const live = document.getElementById("cam");
    const probe = document.createElement("canvas");
    probe.width = 96;
    probe.height = 64;
    const pctx = probe.getContext("2d", { willReadFrequently: true });
    const snap = new Image();
    snap.decoding = "async";
    let inflight = false;
    let cssW = 320;
    let cssH = 200;

    function resize() {
      const wrap = canvas.parentElement;
      cssW = Math.max(1, (wrap && wrap.clientWidth) || canvas.clientWidth || 320);
      cssH = Math.max(1, (wrap && wrap.clientHeight) || canvas.clientHeight || 200);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function pollFrame() {
      if (inflight) return;
      inflight = true;
      snap.onload = () => { inflight = false; };
      snap.onerror = () => { inflight = false; };
      snap.src = "/camera/frame?t=" + Date.now();
    }

    function sourceImage() {
      if (snap.naturalWidth > 4) return snap;
      if (live && live.naturalWidth > 4) return live;
      return null;
    }

    function grab(img) {
      pctx.fillStyle = "#07080c";
      pctx.fillRect(0, 0, 96, 64);
      try {
        pctx.drawImage(img, 0, 0, 96, 64);
        return pctx.getImageData(0, 0, 96, 64);
      } catch (err) {
        return null;
      }
    }

    function sample(data, u, v) {
      const x = Math.max(0, Math.min(95, (u * 95) | 0));
      const y = Math.max(0, Math.min(63, (v * 63) | 0));
      const i = (y * 96 + x) * 4;
      return flyShift(data.data[i], data.data[i + 1], data.data[i + 2]);
    }

    function mapEye(nx, ny, bias) {
      const r2 = nx * nx + ny * ny;
      const k = 0.18;
      const x = nx * (1 + k * r2) * 0.78 + 0.5 + bias;
      const y = ny * (1 + k * r2) * 0.72 + 0.5;
      return [Math.max(0, Math.min(1, x)), Math.max(0, Math.min(1, y))];
    }

    function draw() {
      ctx.fillStyle = "#05060a";
      ctx.fillRect(0, 0, cssW, cssH);

      const eyeR = Math.min(cssW * 0.28, cssH * 0.42);
      const midY = cssH * 0.5;
      const leftC = { x: cssW * 0.29, y: midY };
      const rightC = { x: cssW * 0.71, y: midY };

      ctx.fillStyle = "#120e0c";
      ctx.beginPath();
      ctx.ellipse(cssW * 0.5, midY + eyeR * 0.06, eyeR * 0.42, eyeR * 0.55, 0, 0, Math.PI * 2);
      ctx.fill();

      const img = sourceImage();
      const pixels = img ? grab(img) : null;
      const R = Math.max(4.4, Math.min(7.2, eyeR / 11));
      const hexW = Math.sqrt(3) * R;
      const hexH = 1.5 * R;
      const pad = eyeR + R * 2;

      function paintEye(cx, cy, bias, rim) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, eyeR, 0, Math.PI * 2);
        ctx.clip();
        ctx.fillStyle = "#0a0c10";
        ctx.fillRect(cx - eyeR, cy - eyeR, eyeR * 2, eyeR * 2);

        const x0 = cx - pad;
        const y0 = cy - pad;
        const cols = Math.ceil((pad * 2) / hexW) + 2;
        const rows = Math.ceil((pad * 2) / hexH) + 2;
        for (let row = 0; row < rows; row++) {
          const y = y0 + row * hexH;
          const xOff = (row % 2) * hexW * 0.5;
          for (let col = 0; col < cols; col++) {
            const x = x0 + col * hexW + xOff;
            const dx = (x - cx) / eyeR;
            const dy = (y - cy) / eyeR;
            if (dx * dx + dy * dy > 0.98) continue;
            let rgb = [16, 28, 36];
            if (pixels) {
              const uv = mapEye(dx, dy, bias);
              rgb = sample(pixels, uv[0], uv[1]);
            }
            if (rgb[0] + rgb[1] + rgb[2] < 40) {
              rgb = [16, 26, 34];
            }
            hexPath(ctx, x, y, R * 0.92);
            ctx.fillStyle = "rgb(" + (rgb[0] | 0) + "," + (rgb[1] | 0) + "," + (rgb[2] | 0) + ")";
            ctx.fill();
            ctx.strokeStyle = "rgba(4,6,10,0.72)";
            ctx.lineWidth = 0.9;
            ctx.stroke();
          }
        }

        const gloss = ctx.createRadialGradient(
          cx - eyeR * 0.28, cy - eyeR * 0.34, eyeR * 0.04,
          cx, cy, eyeR
        );
        gloss.addColorStop(0, "rgba(255,255,255,0.12)");
        gloss.addColorStop(0.28, "rgba(255,255,255,0)");
        gloss.addColorStop(1, "rgba(0,0,0,0.1)");
        ctx.fillStyle = gloss;
        ctx.beginPath();
        ctx.arc(cx, cy, eyeR, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.beginPath();
        ctx.arc(cx, cy, eyeR, 0, Math.PI * 2);
        ctx.strokeStyle = rim;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      paintEye(leftC.x, leftC.y, -0.12, "rgba(192,57,43,0.55)");
      paintEye(rightC.x, rightC.y, 0.12, "rgba(192,57,43,0.55)");

      ctx.fillStyle = "rgba(232,237,245,0.7)";
      ctx.font = "11px Avenir Next, Segoe UI, sans-serif";
      ctx.fillText("L", leftC.x - 4, leftC.y + eyeR - 8);
      ctx.fillText("R", rightC.x - 4, rightC.y + eyeR - 8);
    }

    resize();
    requestAnimationFrame(resize);
    window.addEventListener("resize", resize);
    if (window.ResizeObserver && canvas.parentElement) {
      new ResizeObserver(resize).observe(canvas.parentElement);
    }
    pollFrame();
    setInterval(pollFrame, 90);

    let last = 0;
    function loop(t) {
      if (t - last > 50) {
        last = t;
        draw();
      }
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  window.initFlyEye = initFlyEye;
})();
