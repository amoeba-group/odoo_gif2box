/**
 * Removes the page loader once the document is ready.
 *
 * The overlay is rendered up front by the layout so it covers the page from
 * the first paint. A timeout backs the `load` listener up: a single stalled
 * asset must never be able to leave the site hidden behind it.
 */
(function () {
    "use strict";

    var FALLBACK_MS = 6000;

    function hideLoader() {
        var loader = document.getElementById("gif2box_loader");
        if (!loader || loader.dataset.done) {
            return;
        }
        loader.dataset.done = "1";
        loader.classList.add("o_gif2box_loader_done");
        window.setTimeout(function () {
            if (loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
        }, 400);
    }

    if (document.readyState === "complete") {
        hideLoader();
    } else {
        window.addEventListener("load", hideLoader);
    }

    window.setTimeout(hideLoader, FALLBACK_MS);
})();
