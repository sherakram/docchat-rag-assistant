const button = document.getElementById("check-btn");
const result = document.getElementById("result");

button.addEventListener("click", async () => {
  button.disabled = true;
  result.className = "result";
  result.textContent = "Checking...";

  try {
    // Relative path: same server se baat ho rahi hai
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error("Server replied with status " + response.status);
    }
    const data = await response.json();
    result.textContent = "Backend says: " + data.status;
    result.classList.add("ok");
  } catch (error) {
    result.textContent = "Could not reach backend: " + error.message;
    result.classList.add("error");
  } finally {
    button.disabled = false;
  }
});