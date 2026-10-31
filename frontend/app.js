const checkBtn = document.getElementById("check-btn");
const healthResult = document.getElementById("result");

checkBtn.addEventListener("click", async () => {
  checkBtn.disabled = true;
  healthResult.className = "result";
  healthResult.textContent = "Checking...";

  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("Server replied with status " + response.status);
    const data = await response.json();
    healthResult.textContent = "Backend says: " + data.status;
    healthResult.classList.add("ok");
  } catch (error) {
    healthResult.textContent = "Could not reach backend: " + error.message;
    healthResult.classList.add("error");
  } finally {
    checkBtn.disabled = false;
  }
});

const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const uploadResult = document.getElementById("upload-result");

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    showUpload("Please choose a PDF first.", "error");
    return;
  }

  uploadBtn.disabled = true;
  showUpload("Uploading...", "");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Upload failed");
    }
    showUploadSuccess(data);
  } catch (error) {
    showUpload(error.message, "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

function showUpload(message, cssClass) {
  uploadResult.className = "result " + cssClass;
  uploadResult.textContent = message;
}

function showUploadSuccess(data) {
  uploadResult.className = "result ok";
  uploadResult.textContent = "";

  const summary = document.createElement("div");
  summary.textContent =
    data.filename + ": " + data.page_count + " pages, " +
    data.pages_with_text + " with text, " + data.chunk_count + " chunks indexed";

  const preview = document.createElement("div");
  preview.className = "preview";
  preview.textContent = "Preview (page " + data.preview_page + "):\n" + data.preview;

  uploadResult.append(summary, preview);
}