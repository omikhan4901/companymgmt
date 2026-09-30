// Applies the saved colour mode and accent before the first paint.
// Light mode and the plum accent are the defaults.
try {
  var root = document.documentElement;
  var mode = localStorage.getItem("cm.theme");
  if (mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches)) {
    root.classList.add("dark");
  }
  var accent = localStorage.getItem("cm.accent");
  if (accent === "saffron" || accent === "garnet" || accent === "ink") root.setAttribute("data-accent", accent);
} catch (e) {
  // Storage can be blocked; keep the defaults.
}
