(() => {
  const body = document.body;
  const sidebar = document.getElementById("portal-sidebar");
  const toggle = document.getElementById("portal-sidebar-toggle");
  if (!body || !sidebar || !toggle) {
    return;
  }

  const STORAGE_KEY = "hs_sidebar_collapsed";
  const DESKTOP_QUERY = window.matchMedia("(min-width: 981px)");
  const navLinks = Array.from(sidebar.querySelectorAll(".sidebar-nav a[data-nav-label]"));

  function syncCollapsedTooltips(isCollapsed) {
    navLinks.forEach((link) => {
      const label = (link.getAttribute("data-nav-label") || "").trim();
      if (!label) {
        return;
      }
      if (isCollapsed) {
        link.setAttribute("title", label);
      } else {
        link.removeAttribute("title");
      }
    });
  }

  function applyCollapsed(collapsed, persist) {
    const isDesktop = DESKTOP_QUERY.matches;
    if (!isDesktop) {
      body.classList.remove("sidebar-collapsed");
      toggle.setAttribute("aria-expanded", "true");
      syncCollapsedTooltips(false);
      return;
    }

    const nextCollapsed = !!collapsed;
    body.classList.toggle("sidebar-collapsed", nextCollapsed);
    toggle.setAttribute("aria-expanded", nextCollapsed ? "false" : "true");
    syncCollapsedTooltips(nextCollapsed);
    if (persist) {
      try {
        window.localStorage.setItem(STORAGE_KEY, nextCollapsed ? "1" : "0");
      } catch (_storageError) {
        // Ignore storage failures (private mode, disabled storage, etc.).
      }
    }
  }

  function loadPreference() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (_storageError) {
      return false;
    }
  }

  applyCollapsed(loadPreference(), false);

  toggle.addEventListener("click", () => {
    const next = !body.classList.contains("sidebar-collapsed");
    applyCollapsed(next, true);
  });

  const onViewportChange = () => {
    if (!DESKTOP_QUERY.matches) {
      applyCollapsed(false, false);
      return;
    }
    applyCollapsed(loadPreference(), false);
  };

  if (typeof DESKTOP_QUERY.addEventListener === "function") {
    DESKTOP_QUERY.addEventListener("change", onViewportChange);
  } else {
    window.addEventListener("resize", onViewportChange);
  }
})();
