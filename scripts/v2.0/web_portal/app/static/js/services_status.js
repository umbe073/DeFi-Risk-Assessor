(function () {
  "use strict";

  function normalize(value, min, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) {
      return min;
    }
    return Math.max(min, Math.min(max, n));
  }

  document.querySelectorAll("[data-meter-width]").forEach(function (node) {
    const width = normalize(node.getAttribute("data-meter-width"), 0, 100);
    node.style.width = width.toFixed(1) + "%";
  });

  document.querySelectorAll("[data-chart-height]").forEach(function (node) {
    const height = normalize(node.getAttribute("data-chart-height"), 8, 100);
    node.style.height = height.toFixed(1) + "%";
  });
})();

