const messagesEl = document.getElementById("messages");
const emptyEl = document.getElementById("empty");
const form = document.getElementById("chat-form");
const questionEl = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const uploadStatus = document.getElementById("upload-status");
const docList = document.getElementById("doc-list");
const panel = document.getElementById("side-panel");
const togglePanelBtn = document.getElementById("toggle-panel");

let busy = false;


function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

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


function addUserMessage(text) {
  const row = el("div", "msg user");
  row.append(el("div", "bubble", text));
  messagesEl.append(row);
  scrollToBottom();
}

function addErrorMessage(text) {
  const row = el("div", "msg assistant");
  row.append(el("div", "bubble error", text));
  messagesEl.append(row);
  scrollToBottom();
}

function showTyping() {
  const row = el("div", "msg assistant");
  const bubble = el("div", "bubble");
  bubble.setAttribute("aria-label", "Assistant is typing");
  bubble.append(el("span", "dot"), el("span", "dot"), el("span", "dot"));
  row.append(bubble);
  messagesEl.append(row);
  scrollToBottom();
  return row;
}

function buildSources(sources) {
  const wrap = el("div", "sources");
  wrap.append(el("span", "sources-label", "Sources"));

  const chips = el("div", "chips");
  wrap.append(chips);

  sources.forEach((source) => {
    const chip = el("button", "chip", source.filename + " · p. " + source.page);
    chip.type = "button";
    chip.setAttribute("aria-expanded", "false");

    const snippet = el("div", "snippet", source.snippet + "…");
    snippet.hidden = true;

    chip.addEventListener("click", () => {
      snippet.hidden = !snippet.hidden;
      chip.setAttribute("aria-expanded", String(!snippet.hidden));
    });

  
    const item = el("div");
    item.append(chip, snippet);
    chips.append(item);
  });

  return wrap;
}

function addAssistantMessage(data) {
  const row = el("div", "msg assistant");
  const bubble = el("div", data.supported ? "bubble" : "bubble not-found");

  if (!data.supported) {
    bubble.append(el("span", "badge", "Not found in your documents"));
    bubble.append(el("div", "", data.answer));
  } else {
    bubble.append(el("div", "", data.answer));
    if (data.sources.length > 0) {
      bubble.append(buildSources(data.sources));
    }
  }

  row.append(bubble);
  messagesEl.append(row);
  scrollToBottom();
}


async function sendQuestion(question) {
  setBusy(true);
  emptyEl.hidden = true;
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
    addErrorMessage(friendlyError(error));
  } finally {
    setBusy(false);
    questionEl.focus();
  }
}

function autoResize() {
  questionEl.style.height = "auto";
  questionEl.style.height = Math.min(questionEl.scrollHeight, 160) + "px";
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


function setUploadStatus(message, cssClass) {
  uploadStatus.className = "status " + (cssClass || "");
  uploadStatus.textContent = message;
}

function addDocToList(data) {
  const item = el("li", "", data.filename);
  item.append(el("span", "meta", data.page_count + " pages · " + data.chunk_count + " chunks"));
  docList.append(item);
}

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    setUploadStatus("Please choose a PDF first.", "error");
    return;
  }

  uploadBtn.disabled = true;
  setUploadStatus("Uploading and indexing... this can take a few seconds.", "");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(readError(data, response.status));

    setUploadStatus("Ready: " + data.filename, "ok");
    addDocToList(data);
    fileInput.value = "";
    panel.classList.remove("open");
    togglePanelBtn.setAttribute("aria-expanded", "false");
  } catch (error) {
    setUploadStatus(friendlyError(error), "error");
  } finally {
    uploadBtn.disabled = false;
  }
});


togglePanelBtn.addEventListener("click", () => {
  const open = panel.classList.toggle("open");
  togglePanelBtn.setAttribute("aria-expanded", String(open));
});