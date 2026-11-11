const $ = (id) => document.getElementById(id);
const messagesEl = $("messages"), emptyEl = $("empty"), form = $("chat-form");
const questionEl = $("question"), sendBtn = $("send-btn"), suggestEl = $("suggest");
const fileInput = $("file-input"), uploadBtn = $("upload-btn"), uploadStatus = $("upload-status");
const docList = $("doc-list"), docsPanel = $("docs-panel"), docsBtn = $("docs-btn");
const docsClose = $("docs-close"), backdrop = $("backdrop"), subtitle = $("subtitle");
const docsCount = $("docs-count"), openUpload = $("open-upload");

let busy = false;
let docCount = 0;
let hasMessages = false;

// Hamesha textContent: LLM ya PDF ka text HTML ban kar chal nahi sakta
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

const scrollToBottom = () => { messagesEl.scrollTop = messagesEl.scrollHeight; };

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
}

function readError(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) return "Please enter a question (up to 1000 characters).";
  return "Something went wrong (status " + status + ").";
}

function friendlyError(error) {
  if (error instanceof TypeError) return "Could not reach the server. Is it running?";
  return error.message;
}

// Thresholds sirf shuruaati andaza hain, apne scores dekh kar badal lena
function matchLabel(similarity) {
  if (similarity >= 0.7) return "Strong match";
  if (similarity >= 0.6) return "Good match";
  return "Possible match";
}

function updateDocsUI() {
  subtitle.textContent = docCount
    ? "Grounded answers · " + docCount + (docCount === 1 ? " document" : " documents")
    : "No documents yet";
  docsCount.textContent = String(docCount);
  docsCount.hidden = docCount === 0;
  suggestEl.hidden = !(docCount > 0 && !hasMessages);
}

// ---------- Documents panel ----------
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

// ---------- Rendering ----------
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
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(readError(data, response.status));
    typing.remove();
    addAssistantMessage(data);
  } catch (error) {
    typing.remove();
    addError(friendlyError(error));
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
function setStatus(message, cssClass) {
  uploadStatus.className = "status " + (cssClass || "");
  uploadStatus.textContent = message;
}

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
    const response = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(readError(data, response.status));

    const item = el("li", "", data.filename);
    item.append(el("span", "meta", data.page_count + " pages · " + data.chunk_count + " chunks"));
    docList.append(item);

    docCount += 1;
    updateDocsUI();
    setStatus("Ready: " + data.filename, "ok");
    fileInput.value = "";
    setPanel(false);
  } catch (error) {
    setStatus(friendlyError(error), "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

updateDocsUI();