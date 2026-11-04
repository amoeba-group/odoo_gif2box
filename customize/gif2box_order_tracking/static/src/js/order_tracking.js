/**
 * "Copy" buttons on the tracking page: the page's own link, the tracking
 * number (`views/tracking_templates.xml`, `copy_button`).
 *
 * Loaded with Odoo's first, small script bundle rather than the large one
 * it fetches once the page has loaded, and the buttons carry
 * `o_no_wait_lazy_js`. Until that bundle arrives Odoo holds a click on a
 * button and replays it afterwards, by then too late for the browser to
 * allow a copy: a tap in the first seconds on a phone did nothing at all.
 *
 * Once copied, the button turns green with a tick and says "Copied", and a
 * tooltip above it says what was copied, for two and a half seconds. The
 * tooltip is a live region, so a screen reader says it too. Where the
 * browser will not copy (the Clipboard API refused and the old copy
 * command too), the text is offered in a prompt, to copy by hand.
 */

(function () {
    "use strict";

    const SHOWN_MS = 2500;

    function legacyCopy(text) {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.top = "0";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        area.setSelectionRange(0, text.length); // iOS ignores `select()`
        try {
            return document.execCommand("copy");
        } catch {
            return false;
        } finally {
            area.remove();
        }
    }

    async function copy(text) {
        if (navigator.clipboard && window.isSecureContext) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch {
                // Refused here: the old way below.
            }
        }
        return legacyCopy(text);
    }

    function showCopied(button) {
        const tip = button.querySelector(".o_g2b_copy_tip");
        if (tip) {
            // Emptied and filled again, so that a screen reader announces it
            // on every copy, not only the first.
            const message = tip.dataset.message || tip.textContent;
            tip.dataset.message = message;
            tip.textContent = "";
            requestAnimationFrame(() => {
                tip.textContent = message;
            });
        }
        button.classList.add("is-copied");
        clearTimeout(button._g2bCopyTimer);
        button._g2bCopyTimer = setTimeout(() => button.classList.remove("is-copied"), SHOWN_MS);
    }

    document.addEventListener("click", async function (ev) {
        const button = ev.target.closest && ev.target.closest(".o_g2b_copy");
        if (!button) {
            return;
        }
        const text = button.dataset.g2bCopy || "";
        if (await copy(text)) {
            showCopied(button);
        } else {
            const label = button.querySelector(".o_g2b_copy_idle");
            window.prompt(label ? label.textContent.trim() : "", text);
        }
    });
})();
