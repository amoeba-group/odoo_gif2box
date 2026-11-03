/**
 * "Copy" buttons on the tracking page: the tracking number, the page's own
 * link (`views/tracking_templates.xml`, `copy_button`).
 *
 * The button says "Copied" for two seconds; both labels are in the page,
 * translated with it. Where the Clipboard API is not allowed (an older
 * browser, a page not served over HTTPS), a hidden text area and the old
 * copy command do it instead.
 */

(function () {
    "use strict";

    function fallbackCopy(text) {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try {
            document.execCommand("copy");
        } finally {
            area.remove();
        }
    }

    document.addEventListener("click", async function (ev) {
        const button = ev.target.closest && ev.target.closest(".o_g2b_copy");
        if (!button) {
            return;
        }
        const text = button.dataset.g2bCopy || "";
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            fallbackCopy(text);
        }
        button.classList.add("is-copied");
        clearTimeout(button._g2bCopyTimer);
        button._g2bCopyTimer = setTimeout(() => button.classList.remove("is-copied"), 2000);
    });
})();
