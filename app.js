const $ = (id) => document.getElementById(id);
const screens = ["start", "capture", "pickup"];
const show = (id) => screens.forEach((s) => $(s).classList.toggle("active", s === id));

let stream = null, photos = [], opts = { date: true, bw: true, text: "" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startSession() {
  show("capture");
  photos = [];
  document.querySelectorAll(".slot").forEach((s, i) => { s.style.backgroundImage = ""; s.textContent = i + 1; });
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
    $("video").srcObject = stream;
  } catch { alert("Camera access is needed for the photobooth."); return quit(); }
  await sleep(500);
  for (let i = 0; i < 3; i++) {
    for (let c = 3; c > 0; c--) { $("countdown").textContent = `Photo ${i + 1} in ${c}s`; await sleep(1000); }
    photos.push(snap());
    const slot = document.querySelector(`.slot[data-i="${i}"]`);
    slot.style.backgroundImage = `url(${photos[i].toDataURL()})`; slot.textContent = "";
    $("flash").classList.add("on"); await sleep(150); $("flash").classList.remove("on");
  }
  stopCamera();
  show("pickup");
  drawStrip();
}

function snap() {
  const v = $("video"), c = document.createElement("canvas");
  c.width = v.videoWidth; c.height = v.videoHeight;
  const ctx = c.getContext("2d");
  ctx.translate(c.width, 0); ctx.scale(-1, 1);           // mirror like the preview
  ctx.drawImage(v, 0, 0);
  return c;
}

function drawStrip() {
  const W = 600, pad = 30, ph = 400, foot = 120;
  const cv = $("strip"), ctx = cv.getContext("2d");
  cv.width = W; cv.height = pad + 3 * (ph + pad) + foot;
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.filter = opts.bw ? "grayscale(1) contrast(1.05)" : "none";
  photos.forEach((p, i) => {
    const w = W - 2 * pad, sx = Math.max(0, (p.width - p.height * w / ph) / 2);
    ctx.drawImage(p, sx, 0, p.width - 2 * sx, p.height, pad, pad + i * (ph + pad), w, ph);
  });
  ctx.filter = "none";
  ctx.fillStyle = "#1A1A2E"; ctx.textAlign = "center"; ctx.font = "24px Inter, sans-serif";
  const y = pad + 3 * (ph + pad) + 30;
  if (opts.date) ctx.fillText(new Date().toLocaleDateString("en-GB"), W / 2, y);
  if (opts.text) ctx.fillText(opts.text, W / 2, y + 36);
}

function save() {
  const a = document.createElement("a");
  a.download = `pyphotobooth-${Date.now()}.png`;
  a.href = $("strip").toDataURL("image/png");
  a.click();
}

function stopCamera() { stream?.getTracks().forEach((t) => t.stop()); stream = null; }
function quit() { stopCamera(); show("start"); }

$("startBtn").onclick = startSession;
$("dateBtn").onclick = (e) => { opts.date = !opts.date; e.target.classList.toggle("on"); drawStrip(); };
$("bwBtn").onclick = (e) => { opts.bw = !opts.bw; e.target.classList.toggle("on"); drawStrip(); };
$("caption").oninput = (e) => { opts.text = e.target.value; drawStrip(); };
$("saveBtn").onclick = save;
$("quitBtn").onclick = quit;

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (e.code === "Space" && $("start").classList.contains("active")) { e.preventDefault(); startSession(); }
  if (["KeyQ", "Escape"].includes(e.code)) quit();
});