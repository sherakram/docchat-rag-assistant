const $ = (id) => document.getElementById(id);
const messagesEl = $("messages"), emptyEl = $("empty"), form = $("chat-form");
const questionEl = $("question"), sendBtn = $("send-btn"), suggestEl = $("suggest");
const fileInput = $("file-input"), uploadBtn = $("upload-btn"), uploadStatus = $("upload-status");
const docList = $("doc-list"), docsPanel = $("docs-panel"), docsBtn = $("docs-btn");
const docsClose = $("docs-close"), backdrop = $("backdrop"), subtitle = $("subtitle");
const docsCount = $("docs-count"), openUpload = $("open-upload");
const scopeBar = $("scope-bar"), scopeEl = $("scope");

let busy = false;
let docs = [];
let hasMessages = false;

// ---------- Helpers ----------
// Hamesha textContent: LLM ya PDF ka text HTML ban kar chal nahi sakta
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

const scrollToBottom = () => { messagesEl.scrollTop = messagesEl.scrollHeight; };

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function readError(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) return "Please enter a question (up to 1000 characters).";
  return "Something went wrong (status " + status + ").";
}

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(readError(data, response.status), response.status);
  return data;
}

function friendlyError(error) {
  if (error instanceof TypeError) return "Could not reach the server. Is it running?";
  return error.message;
}

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
}

function setStatus(message, cssClass) {
  uploadStatus.className = "status " + (cssClass || "");
  uploadStatus.textContent = message;
}

function formatDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return isNaN(date) ? "" : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Thresholds sirf shuruaati andaza hain, apne scores dekh kar badal lena
function matchLabel(similarity) {
  if (similarity >= 0.7) return "Strong match";
  if (similarity >= 0.6) return "Good match";
  return "Possible match";
}

// ---------- Documents panel (bottom sheet) ----------
function setPanel(open) {
  docsPanel.classList.toggle("open", open);
  backdrop.hidden = !open;
  docsBtn.setAttribute("aria-expanded", String(open));
  if (open) fileInput.focus();
}
docsBtn.addEventListener("click", () => setPanel(!docsPanel.classList.contains("open")));
docsClose.addEventListener("click", () => { setPanel(false); docsBtn.focus(); });
backdrop.addEventListener("click", () => setPanel(false));
openUpload.addEventListener("click", () => setPanel(true));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && docsPanel.classList.contains("open")) {
    setPanel(false);
    docsBtn.focus();
  }
});

// ---------- Document list, scope, delete ----------
function updateDocsUI() {
  const count = docs.length;
  subtitle.textContent = count
    ? "Grounded answers · " + count + (count === 1 ? " document" : " documents")
    : "No documents yet";
  docsCount.textContent = String(count);
  docsCount.hidden = count === 0;
  suggestEl.hidden = !(count > 0 && !hasMessages);
}

function renderScope() {
  const previous = scopeEl.value;
  scopeEl.replaceChildren(new Option("All documents", ""));
  docs.forEach((doc) => scopeEl.append(new Option(doc.filename, doc.doc_id)));
  scopeEl.value = docs.some((d) => d.doc_id === previous) ? previous : "";
  scopeBar.hidden = docs.length < 2; // scope sirf tab jab 2+ documents hon
}

function renderDocs() {
  docList.replaceChildren();
  docs.forEach((doc) => {
    const item = el("li", "doc-item");

    const info = el("div", "doc-info");
    info.append(el("span", "doc-name", doc.filename));
    const parts = [doc.page_count + " pages", doc.chunk_count + " chunks"];
    const date = formatDate(doc.uploaded_at);
    if (date) parts.push(date);
    info.append(el("span", "meta", parts.join(" · ")));

    const del = el("button", "del", "Delete");
    del.type = "button";
    del.setAttribute("aria-label", "Delete " + doc.filename);
    del.addEventListener("click", () => onDeleteClick(doc, del));

    item.append(info, del);
    docList.append(item);
  });
}

async function loadDocuments() {
  try {
    const data = await api("/api/documents");
    docs = data.documents;
  } catch (error) {
    setStatus(friendlyError(error), "error");
    return;
  }
  renderDocs();
  renderScope();
  updateDocsUI();
}

// Do-step delete: pehli click "Confirm?", 4 second ke andar doosri click par delete
function onDeleteClick(doc, button) {
  if (button.dataset.armed !== "1") {
    button.dataset.armed = "1";
    button.textContent = "Confirm?";
    button.classList.add("armed");
    setTimeout(() => {
      if (!button.isConnected) return;
      button.dataset.armed = "";
      button.textContent = "Delete";
      button.classList.remove("armed");
    }, 4000);
    return;
  }
  deleteDocument(doc, button);
}

async function deleteDocument(doc, button) {
  button.disabled = true;
  try {
    await api("/api/documents/" + doc.doc_id, { method: "DELETE" });
    setStatus("Deleted: " + doc.filename, "ok");
  } catch (error) {
    setStatus(friendlyError(error), "error");
  }
  await loadDocuments(); // list hamesha server se dobara lo
}

// ---------- Rendering messages ----------
function addUserMessage(text) {
  const row = el("div", "msg user");
  row.append(el("div", "bubble", text));
  messagesEl.append(row);
  scrollToBottom();
}

function showTyping() {
  const row = el("div", "msg");
  const card = el("div", "card");
  card.setAttribute("aria-label", "Assistant is typing");
  card.append(el("span", "dot"), el("span", "dot"), el("span", "dot"));
  row.append(card);
  messagesEl.append(row);
  scrollToBottom();
  return row;
}

function addError(text) {
  const row = el("div", "msg");
  row.append(el("div", "card err", text));
  messagesEl.append(row);
  scrollToBottom();
}

function buildEvidence(sources) {
  const wrap = el("div");
  wrap.append(el("div", "ev-label", "EVIDENCE"));
  const list = el("div", "ev-list");

  sources.forEach((source) => {
    const card = el("div", "ev");
    card.append(el("div", "pg", "p." + source.page));

    const body = el("div", "ev-body");
    body.append(el("div", "ev-name", source.filename));
    body.append(el("div", "ev-snip", "…" + source.snippet + "…"));

    const match = el("div", "match");
    const track = el("div", "track");
    const fill = el("div", "fill");
    fill.style.width = Math.max(4, Math.min(100, Math.round(source.similarity * 100))) + "%";
    track.append(fill);
    match.append(track, el("span", "", matchLabel(source.similarity)));
    body.append(match);

    card.append(body);
    list.append(card);
  });

  wrap.append(list);
  return wrap;
}

function addAssistantMessage(data) {
  const row = el("div", "msg");
  const stack = el("div", "stack");

  if (data.supported) {
    const count = data.sources.length;
    const card = el("div", "card");
    card.append(el("span", "badge", "Grounded in " + count + (count === 1 ? " page" : " pages")));
    card.append(el("div", "answer", data.answer));
    stack.append(card);
    if (count > 0) stack.append(buildEvidence(data.sources));
  } else {
    const card = el("div", "card nf");
    card.append(el("span", "badge warn", "Not found in your documents"));
    card.append(el("div", "answer", data.answer));
    stack.append(card);
  }

  row.append(stack);
  messagesEl.append(row);
  scrollToBottom();
}

// ---------- Asking ----------
async function sendQuestion(question) {
  setBusy(true);
  hasMessages = true;
  emptyEl.hidden = true;
  updateDocsUI();
  addUserMessage(question);
  const typing = showTyping();

  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, doc_id: scopeEl.value || null }),
    });
    typing.remove();
    addAssistantMessage(data);
  } catch (error) {
    typing.remove();
    addError(friendlyError(error));
    // Jis document par sawal tha wo gayab? List dobara lo, scope khud "All" par aa jayega
    if (error instanceof ApiError && error.status === 404) await loadDocuments();
  } finally {
    setBusy(false);
    questionEl.focus();
  }
}

function autoResize() {
  questionEl.style.height = "auto";
  questionEl.style.height = Math.min(questionEl.scrollHeight, 144) + "px";
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question || busy) return;
  questionEl.value = "";
  autoResize();
  sendQuestion(question);
});

questionEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});
questionEl.addEventListener("input", autoResize);

suggestEl.addEventListener("click", (event) => {
  const chip = event.target.closest("button[data-q]");
  if (chip && !busy) sendQuestion(chip.dataset.q);
});

// ---------- Upload ----------
uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    setStatus("Please choose a PDF first.", "error");
    return;
  }

  uploadBtn.disabled = true;
  setStatus("Uploading and indexing… this can take a few seconds.", "");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const data = await api("/api/upload", { method: "POST", body: formData });
    fileInput.value = "";
    await loadDocuments();
    setStatus("Ready: " + data.filename, "ok");
    setPanel(false);
  } catch (error) {
    setStatus(friendlyError(error), "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

// ---------- Start ----------
loadDocuments();