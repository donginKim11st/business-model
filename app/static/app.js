document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#genbtn");
  if (!btn) return;
  const uid = btn.dataset.uid;
  const out = document.getElementById("draft");
  btn.disabled = true;
  out.innerHTML = "<p class=muted>생성 중…</p>";
  try {
    const r = await fetch(`/product/${encodeURIComponent(uid)}/draft`, { method: "POST" });
    out.innerHTML = await r.text();
    btn.textContent = "다시 생성";
  } catch {
    out.innerHTML = "<p class=err>생성 실패. 다시 시도해 주세요.</p>";
  } finally {
    btn.disabled = false;
  }
});
