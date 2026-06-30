document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#genbtn");
  if (!btn) return;
  const uid = btn.dataset.uid;
  const out = document.getElementById("draft");
  btn.disabled = true;
  out.innerHTML = "<p class=muted>생성 중…</p>";
  try {
    const r = await fetch(`/product/${encodeURIComponent(uid)}/draft`, { method: "POST" });
    if (!r.ok) throw new Error(r.status);
    out.innerHTML = await r.text();
    btn.textContent = "다시 생성";
  } catch {
    out.innerHTML = "<p class=err>생성 실패. 다시 시도해 주세요.</p>";
  } finally {
    btn.disabled = false;
  }
});

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#exportbtn");
  if (!btn) return;
  const uid = btn.dataset.uid;
  const draftEl = document.getElementById("draft-json");
  if (!draftEl) return;
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "이미지 생성 중…";
  try {
    const fd = new FormData();
    fd.append("draft", draftEl.textContent);
    document.querySelectorAll("input[data-slot]").forEach((inp) => {
      if (inp.files[0]) fd.append(inp.dataset.slot, inp.files[0]);
    });
    const r = await fetch(`/product/${encodeURIComponent(uid)}/detail-image`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(r.status);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "상세페이지.png";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    btn.textContent = "다시 내보내기";
  } catch {
    alert("이미지 생성 실패. 다시 시도해 주세요.");
    btn.textContent = orig;
  } finally {
    btn.disabled = false;
  }
});
