/**
 * The sign-in pages (`views/auth_templates.xml`): a button in each
 * password field to show what was typed, which on a phone saves typing it
 * twice for nothing. Labels from the page, translated there.
 */
(function () {
    "use strict";

    const EYE = '<svg class="o_g2b_pw_show" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>'
        + '<svg class="o_g2b_pw_hide" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/></svg>';

    function start() {
        const root = document.querySelector(".o_g2b_auth");
        if (!root) {
            return;
        }
        const text = (key) => {
            const el = root.querySelector(`[data-g2b-msg="${key}"]`);
            return el ? el.textContent.trim() : "";
        };
        root.querySelectorAll('input[type="password"]').forEach((input) => {
            const wrap = document.createElement("div");
            wrap.className = "o_g2b_pw";
            input.parentNode.insertBefore(wrap, input);
            wrap.appendChild(input);
            const button = document.createElement("button");
            button.type = "button";
            button.className = "o_g2b_pw_toggle o_no_wait_lazy_js";
            button.innerHTML = EYE;
            button.setAttribute("aria-label", text("show"));
            button.setAttribute("aria-pressed", "false");
            button.addEventListener("click", () => {
                const shown = input.type === "password";
                input.type = shown ? "text" : "password";
                button.classList.toggle("is-shown", shown);
                button.setAttribute("aria-pressed", shown ? "true" : "false");
                button.setAttribute("aria-label", text(shown ? "hide" : "show"));
                input.focus();
            });
            wrap.appendChild(button);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
