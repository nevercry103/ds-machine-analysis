// Theme — light/dark toggle with localStorage persistence.
//
// The OS-level preference is the default; an explicit user choice
// (the toggle button) wins and is persisted under "dsma.theme".
// Pages should call applyTheme() before first paint to avoid flash.

const KEY = "dsma.theme";

export function applyTheme(t) {
  const html = document.documentElement;
  if (t === "dark" || t === "light") {
    html.setAttribute("data-theme", t);
  } else {
    html.removeAttribute("data-theme");
  }
}

export function loadTheme() {
  return localStorage.getItem(KEY); // "dark" | "light" | null
}

export function saveTheme(t) {
  if (t === "dark" || t === "light") localStorage.setItem(KEY, t);
  else localStorage.removeItem(KEY);
}

export function currentEffectiveTheme() {
  const stored = loadTheme();
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function toggleTheme() {
  const next = currentEffectiveTheme() === "dark" ? "light" : "dark";
  saveTheme(next);
  applyTheme(next);
  return next;
}

export function attachToggle(button) {
  if (!button) return;
  const update = () => {
    const t = currentEffectiveTheme();
    button.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    button.title = t === "dark" ? "Switch to light mode" : "Switch to dark mode";
    button.textContent = t === "dark" ? "☀" : "☾";
  };
  button.addEventListener("click", () => {
    toggleTheme();
    update();
  });
  update();
}

// Initial paint — call as early as possible (before <body>).
applyTheme(loadTheme());
