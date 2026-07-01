// 추천 사진: 슬롯별로 선택된 이미지 data URI 보관 (업로드 파일이 없을 때 export에 사용)
const chosenPhotos = {};

function dataUriToBlob(dataUri) {
  const [meta, b64] = dataUri.split(",");
  const mime = (meta.match(/data:(.*?);base64/) || [, "image/jpeg"])[1];
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

function clearChosen(slot) {
  delete chosenPhotos[slot];
  const preview = document.querySelector(`.slot-preview[data-slot="${slot}"]`);
  if (preview) { preview.hidden = true; preview.textContent = ""; }
}

// 상세페이지 초안 생성
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
    Object.keys(chosenPhotos).forEach((k) => delete chosenPhotos[k]);   // 새 초안 → 추천 상태 초기화
    btn.textContent = "다시 생성";
  } catch {
    out.innerHTML = "<p class=err>생성 실패. 다시 시도해 주세요.</p>";
  } finally {
    btn.disabled = false;
  }
});

// 이미지로 내보내기
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
    const styleEl = document.querySelector("input[name=style]:checked");
    if (styleEl) fd.append("style", styleEl.value);
    document.querySelectorAll("input[data-slot]").forEach((inp) => {
      if (inp.files[0]) fd.append(inp.dataset.slot, inp.files[0]);
    });
    Object.keys(chosenPhotos).forEach((slot) => {
      const inp = document.getElementById(`slot-${slot}`);
      if (inp && inp.files[0]) return;              // 업로드 파일이 있으면 그걸 우선
      fd.append(slot, dataUriToBlob(chosenPhotos[slot]), `${slot}.jpg`);
    });
    const r = await fetch(`/product/${encodeURIComponent(uid)}/detail-image`, { method: "POST", body: fd });
    if (!r.ok) {
      const msg = await r.text().catch(() => "");
      throw new Error(msg || `오류 ${r.status}`);
    }
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
  } catch (err) {
    alert("이미지 생성 실패: " + (err && err.message ? err.message : "다시 시도해 주세요."));
    btn.textContent = orig;
  } finally {
    btn.disabled = false;
  }
});

// 파일 업로드 시 해당 슬롯의 추천 선택 해제(양방향 동기화)
document.addEventListener("change", (e) => {
  const inp = e.target.closest("input[data-slot]");
  if (inp && inp.files[0]) clearChosen(inp.dataset.slot);
});

// 슬롯별 "사진 추천" — 네이버 이미지 후보를 그리드로 (DOM API로 안전 구성)
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".suggest-btn");
  if (!btn) return;
  const uid = btn.dataset.uid, slot = btn.dataset.slot;
  const panel = document.querySelector(`.suggest-panel[data-slot="${slot}"]`);
  if (!panel) return;
  panel.hidden = false;
  panel.textContent = "추천 이미지를 불러오는 중…";
  try {
    const r = await fetch(`/product/${encodeURIComponent(uid)}/photo-suggest?slot=${encodeURIComponent(slot)}`);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `오류 ${r.status}`);
    const items = body.items || [];
    panel.textContent = "";
    if (!items.length) { panel.textContent = "검색 결과가 없습니다."; return; }
    const note = document.createElement("p");
    note.className = "suggest-note";
    note.textContent = "클릭하면 이 슬롯에 반영됩니다 · 타인 저작권/상업이용은 셀러 책임";
    const grid = document.createElement("div");
    grid.className = "suggest-grid";
    items.forEach((it) => {
      if (!it || !it.link) return;
      const img = document.createElement("img");         // 프로퍼티 대입 → HTML 파싱 없음(XSS 불가)
      img.className = "suggest-thumb";
      img.src = it.thumbnail || "";
      img.alt = "추천";
      img.dataset.link = it.link;
      img.dataset.slot = slot;
      img.dataset.uid = uid;
      grid.appendChild(img);
    });
    panel.appendChild(note);
    panel.appendChild(grid);
  } catch (err) {
    panel.textContent = "추천 실패: " + (err && err.message ? err.message : "");
  }
});

// 추천 썸네일 클릭 → 원본 fetch → 슬롯에 반영(DOM API로 미리보기)
document.addEventListener("click", async (e) => {
  const thumb = e.target.closest(".suggest-thumb");
  if (!thumb) return;
  const uid = thumb.dataset.uid, slot = thumb.dataset.slot, link = thumb.dataset.link;
  const preview = document.querySelector(`.slot-preview[data-slot="${slot}"]`);
  thumb.classList.add("loading");
  try {
    const fd = new FormData();
    fd.append("url", link);
    const r = await fetch(`/product/${encodeURIComponent(uid)}/photo-fetch`, { method: "POST", body: fd });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `오류 ${r.status}`);
    chosenPhotos[slot] = body.data_uri;
    const fileInp = document.getElementById(`slot-${slot}`);
    if (fileInp) fileInp.value = "";                 // 추천 선택이 업로드를 대체
    if (preview) {
      preview.hidden = false;
      preview.textContent = "";
      const img = document.createElement("img");     // data URI를 프로퍼티로 대입 → 속성 탈출 불가
      img.src = body.data_uri;
      img.alt = "선택됨";
      const tag = document.createElement("span");
      tag.className = "chosen-tag";
      tag.textContent = "추천 반영됨";
      preview.appendChild(img);
      preview.appendChild(tag);
    }
    const panel = document.querySelector(`.suggest-panel[data-slot="${slot}"]`);
    if (panel) panel.hidden = true;
  } catch (err) {
    alert("사진 반영 실패: " + (err && err.message ? err.message : ""));
  } finally {
    thumb.classList.remove("loading");
  }
});
