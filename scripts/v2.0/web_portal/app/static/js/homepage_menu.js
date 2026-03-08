(function () {
  const menuOpen = document.getElementById("hsl-menu-open");
  const menuOverlay = document.getElementById("hsl-menu-overlay");
  const menuClose = document.getElementById("hsl-menu-close");
  const menuCloseBackdrop = document.getElementById("hsl-menu-close-backdrop");
  if (!menuOpen || !menuOverlay || !menuClose || !menuCloseBackdrop) return;

  const openMenu = () => {
    menuOverlay.hidden = false;
    document.body.classList.add("hsl-lock-scroll");
  };

  const closeMenu = () => {
    menuOverlay.hidden = true;
    document.body.classList.remove("hsl-lock-scroll");
  };

  menuOpen.addEventListener("click", openMenu);
  menuClose.addEventListener("click", closeMenu);
  menuCloseBackdrop.addEventListener("click", closeMenu);
  menuOverlay.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
})();
