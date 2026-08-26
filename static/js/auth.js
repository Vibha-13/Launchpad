(function () {
  const form = document.getElementById("auth-form");
  if (!form) return;

  const errorBox = document.getElementById("error-box");
  const overlay = document.getElementById("splash-overlay");
  const submitBtn = form.querySelector("button[type=submit]");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.innerHTML = "";
    submitBtn.disabled = true;

    const payload = {};
    new FormData(form).forEach((value, key) => { payload[key] = value; });

    try {
      const res = await fetch(form.getAttribute("action"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        errorBox.innerHTML = `<p class="error">${escapeHtml(data.error || "Something went wrong. Please try again.")}</p>`;
        submitBtn.disabled = false;
        return;
      }

      showSplash();
    } catch (err) {
      errorBox.innerHTML = `<p class="error">Couldn't reach the server. Please try again.</p>`;
      submitBtn.disabled = false;
    }
  });

  function showSplash() {
    overlay.classList.add("show");
    setTimeout(() => {
      window.location.href = "/dashboard";
    }, 850);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();
