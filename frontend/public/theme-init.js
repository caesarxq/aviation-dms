/* Apply the saved theme before the React bundle paints to avoid a light/dark flash. */
(() => {
  let preference = "system";
  try {
    const stored = window.localStorage.getItem("kfl-theme");
    if (stored === "light" || stored === "dark" || stored === "system") preference = stored;
  } catch {
    // Fall back to the OS preference when browser storage is unavailable.
  }
  const dark = preference === "dark" || (
    preference === "system" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
  );
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0d2235" : "#f5f7fa");
})();
