/**
 * Fetch the hero's other slides once the page has loaded.
 *
 * Only the first slide's pictures are loaded with the page; the others are
 * marked `loading="lazy"` so they do not compete with it. A lazy picture on a
 * hidden slide, though, would only start downloading when its slide came up,
 * and that slide would open on the blurred placeholder. So once the page is
 * done, and the browser is idle, they are switched to eager: by the time the
 * carousel turns (every six seconds) they are already there.
 */

(function () {
    "use strict";

    function warmUp() {
        document.querySelectorAll('#o_g2b_hero img[loading="lazy"]').forEach((img) => {
            img.loading = "eager";
        });
    }

    function schedule() {
        if (window.requestIdleCallback) {
            window.requestIdleCallback(warmUp, { timeout: 3000 });
        } else {
            setTimeout(warmUp, 1000);
        }
    }

    if (document.readyState === "complete") {
        schedule();
    } else {
        window.addEventListener("load", schedule, { once: true });
    }
})();
