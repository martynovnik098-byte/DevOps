/* Интерфейс «Заметок»: минимум зависимостей, чистый JS. */

const $ = (selector) => document.querySelector(selector);
const listEl = $("#notes");
let notes = [];
let hideDone = false;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || res.statusText);
  return body;
}

async function reload() {
  notes = await api("/api/notes");
  render();
}

function render() {
  const visible = hideDone ? notes.filter((n) => !n.done) : notes;
  const done = notes.filter((n) => n.done).length;
  $("#counter").textContent =
    `Заметок: ${visible.length}, выполнено: ${done}` +
    (hideDone ? ` (показаны не все)` : "");
  $("#empty").classList.toggle("hidden", visible.length > 0);
  listEl.replaceChildren(...visible.map(noteCard));
}

function noteCard(note) {
  const card = document.createElement("article");
  card.className = "card note" + (note.done ? " done" : "");
  card.dataset.id = note.id;

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = !!note.done;
  checkbox.title = "Отметить выполненной";
  checkbox.onchange = () => update(note.id, { done: checkbox.checked });

  const body = document.createElement("div");
  body.className = "note-body";

  const title = document.createElement("h3");
  title.textContent = note.title;

  const text = document.createElement("p");
  text.textContent = note.text || "без текста";
  if (!note.text) text.classList.add("muted");

  const meta = document.createElement("small");
  meta.className = "muted";
  meta.textContent =
    `создана ${fmt(note.created_at)} · изменена ${fmt(note.updated_at)}`;

  body.append(title, text, meta);

  const actions = document.createElement("div");
  actions.className = "actions";
  actions.append(
    button("Изменить", () => startEdit(card, note)),
    button("Удалить", () => remove(note.id)),
  );

  card.append(checkbox, body, actions);
  return card;
}

function startEdit(card, note) {
  const form = document.createElement("div");
  form.className = "edit";

  const title = document.createElement("input");
  title.value = note.title;
  title.maxLength = 120;

  const text = document.createElement("textarea");
  text.rows = 3;
  text.value = note.text || "";

  const row = document.createElement("div");
  row.className = "actions";
  const save = button("Сохранить", async () => {
    await update(note.id, {
      title: title.value.trim() || note.title,
      text: text.value.trim(),
    });
  });
  save.classList.add("primary");
  const cancel = button("Отмена", render);
  row.append(save, cancel);

  form.append(title, text, row);
  card.replaceChildren(form);
  title.focus();
}

function button(label, onClick) {
  const el = document.createElement("button");
  el.className = "btn";
  el.textContent = label;
  el.onclick = onClick;
  return el;
}

async function update(id, patch) {
  await api(`/api/notes/${id}`, { method: "PUT", body: JSON.stringify(patch) });
  await reload();
}

async function remove(id) {
  await api(`/api/notes/${id}`, { method: "DELETE" });
  await reload();
}

function fmt(iso) {
  return new Date(iso).toLocaleString("ru-RU");
}

$("#note-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("#title");
  const text = $("#text");
  try {
    await api("/api/notes", {
      method: "POST",
      body: JSON.stringify({ title: title.value.trim(), text: text.value.trim() }),
    });
    title.value = "";
    text.value = "";
    await reload();
  } catch (err) {
    alert("Не удалось добавить заметку: " + err.message);
  }
});

$("#hide-done").addEventListener("change", (event) => {
  hideDone = event.target.checked;
  render();
});

async function refreshStats() {
  try {
    const s = await api("/api/stats");
    $("#stats").textContent =
      `v${s.version} · заметок: ${s.notes} · uptime: ${s.uptime_seconds} c · ` +
      `health: /health · метрики: /metrics`;
  } catch {
    $("#stats").textContent = "приложение недоступно";
  }
}

reload().catch((err) => console.error(err));
refreshStats();
setInterval(refreshStats, 5000);
