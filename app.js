const $ = (id) => document.getElementById(id);
const screens = ["start", "capture", "pickup"];
const show = (id) => screens.forEach((s) => $(s).classList.toggle("active", s === id));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let stream = null;
let photos = [];
let stripFile = null;   // ready-made PNG for sharing
let running = false;
const opts = { date: true, bw: true, text: "" };

/* ---------- CAPTURE ---------- */
async function startSession() {
  if (running) return;
  running = true;
  show("capture");
  photos = [];
  stripFile = null;
  document.querySelectorAll(".slot").forEach((s, i) => {
    s.style.backgroundImage = "";
    s.textContent = i + 1;
  });

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
      audio: false,
    });
    $("video").srcObject = stream;
    await $("video").play();
  } catch {
    alert("Camera access is needed for the photobooth.");
    return quit();
  }

  await sleep(500);
  for (let i = 0; i < 3; i++) {
    for (let c = 3; c > 0; c--) {
      if (!running) return;
      $("countdown").textContent = `Photo ${i + 1} in ${c}s`;
      await sleep(1000);
    }
    if (!running) return;
    photos.push(snap());
    const slot = document.querySelector(`.slot[data-i="${i}"]`);
    slot.style.backgroundImage = `url(${photos[i].toDataURL("image/jpeg", 0.85)})`;
    slot.textContent = "";
    $("flash").classList.add("on");
    await sleep(150);
    $("flash").classList.remove("on");
  }

  $("countdown").textContent = "";
  stopCamera();
  running = false;
  show("pickup");
  drawStrip();
}

function snap() {
  const v = $("video");
  const c = document.createElement("canvas");
  c.width = v.videoWidth;
  c.height = v.videoHeight;
  const ctx = c.getContext("2d");
  ctx.translate(c.width, 0);   // mirror like the preview
  ctx.scale(-1, 1);
  ctx.drawImage(v, 0, 0);
  return c;
}

/* ---------- STRIP ---------- */
function drawStrip() {
  if (!photos.length) return;
  const W = 600, pad = 30, ph = 304, foot = 120;   // 540 × 304 ≈ 16:9
  const cv = $("strip");
  const ctx = cv.getContext("2d");
  cv.width = W;
  cv.height = pad + 3 * (ph + pad) + foot;

  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, cv.width, cv.height);

  ctx.filter = opts.bw ? "grayscale(1) contrast(1.05)" : "none";
  photos.forEach((p, i) => {
    const w = W - 2 * pad;
    const srcW = Math.min(p.width, (p.height * w) / ph);   // crop to frame shape
    const srcH = (srcW * ph) / w;
    const sx = (p.width - srcW) / 2;
    const sy = (p.height - srcH) / 2;
    ctx.drawImage(p, sx, sy, srcW, srcH, pad, pad + i * (ph + pad), w, ph);
  });
  ctx.filter = "none";

  ctx.fillStyle = "#1A1A2E";
  ctx.textAlign = "center";
  ctx.font = "24px Inter, system-ui, sans-serif";
  const y = pad + 3 * (ph + pad) + 30;
  if (opts.date) ctx.fillText(new Date().toLocaleDateString("en-GB"), W / 2, y);
  if (opts.text) ctx.fillText(opts.text, W / 2, opts.date ? y + 36 : y);

  // prepare the file now so SAVE can open the share sheet instantly
  cv.toBlob((b) => {
    stripFile = new File([b], `pyphotobooth-${Date.now()}.png`, { type: "image/png" });
  }, "image/png");
}

/* ---------- SAVE (download) ---------- */
function download() {
  const a = document.createElement("a");
  a.download = `pyphotobooth-${Date.now()}.png`;
  a.href = $("strip").toDataURL("image/png");
  a.click();
}

/* ---------- SHARE (AirDrop, Save Image, Messages...) ---------- */
const canShareFiles = !!navigator.canShare?.({
  files: [new File([""], "test.png", { type: "image/png" })],
});
$("shareBtn").hidden = !canShareFiles;   // hide where the browser has no share sheet

async function share() {
  if (!stripFile) return;   // strip still being prepared
  try {
    await navigator.share({ files: [stripFile], title: "PyPhotobooth" });
  } catch (err) {
    if (err.name !== "AbortError") download();   // share failed: fall back to download
  }
}

/* ---------- QUIT ---------- */
function stopCamera() {
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  $("video").srcObject = null;
}

function quit() {
  running = false;
  stopCamera();
  $("countdown").textContent = "";
  show("start");
}

/* ---------- EVENTS ---------- */
$("startBtn").onclick = startSession;
$("dateBtn").onclick = (e) => { opts.date = !opts.date; e.currentTarget.classList.toggle("on"); drawStrip(); };
$("bwBtn").onclick = (e) => { opts.bw = !opts.bw; e.currentTarget.classList.toggle("on"); drawStrip(); };
$("caption").oninput = (e) => { opts.text = e.target.value; drawStrip(); };
$("saveBtn").onclick = download;
$("shareBtn").onclick = share;
$("quitBtn").onclick = quit;

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (e.code === "Space" && $("start").classList.contains("active")) {
    e.preventDefault();
    startSession();
  }
  if (e.code === "KeyQ" || e.code === "Escape") quit();
});