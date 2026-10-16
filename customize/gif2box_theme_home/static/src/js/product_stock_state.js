/**
 * Product page: the buy form when the product cannot be bought, and the
 * wishlist heart on the picture.
 *
 * Buy form
 * --------
 * `website_sale_stock` marks `#o_wsale_cta_wrapper` with `out_of_stock` when
 * the current variant or combo cannot be bought, and hid it; the stylesheet
 * now keeps it on screen, faded (`product_page.scss`). Fading is only what
 * it looks like, so here the controls are taken out of the tab order and
 * announced as disabled, and clicks are stopped before Odoo's handlers see
 * them: `pointer-events` alone would still let a keyboard press through. The
 * class is watched rather than set here, because Odoo re-evaluates it on
 * every variant change.
 *
 * Wishlist heart
 * --------------
 * `.o_g2b_wish_on_image` (`views/product_templates.xml`) presses Odoo's own
 * button, which stays hidden in the buy form because Odoo's script finds the
 * product from there. Odoo disables its button once the variant is in the
 * wishlist, and re-enables it for a variant that is not; the heart follows.
 */

(function () {
    "use strict";

    function setupBuyForm(wrapper) {
        const sync = () => {
            const unavailable = wrapper.classList.contains("out_of_stock");
            for (const control of wrapper.querySelectorAll("a.btn, button.btn")) {
                if (unavailable) {
                    control.setAttribute("aria-disabled", "true");
                    control.setAttribute("tabindex", "-1");
                } else {
                    control.removeAttribute("aria-disabled");
                    control.removeAttribute("tabindex");
                }
            }
            const quantity = wrapper.querySelector("input.quantity");
            if (quantity) {
                quantity.readOnly = unavailable;
                quantity.tabIndex = unavailable ? -1 : 0;
            }
        };

        // Capture phase, on the wrapper: Odoo's handlers are delegated from
        // an ancestor, so stopping the event here means they never run.
        wrapper.addEventListener("click", (ev) => {
            if (wrapper.classList.contains("out_of_stock")) {
                ev.preventDefault();
                ev.stopPropagation();
            }
        }, true);

        new MutationObserver(sync).observe(wrapper, {
            attributes: true,
            attributeFilter: ["class"],
        });
        sync();
    }

    function setupWishlistHeart(heart) {
        const original = document.querySelector("#product_details .o_add_wishlist_dyn");
        if (!original) {
            heart.remove();
            return;
        }
        // Odoo's button is about to be hidden; the heart is the one to show.
        document.documentElement.classList.add("o_g2b_wish_moved");

        const sync = () => {
            const inWishlist = original.disabled || original.classList.contains("disabled");
            heart.classList.toggle("o_g2b_wish_active", inWishlist);
            heart.setAttribute("aria-pressed", inWishlist ? "true" : "false");
            // The two labels are rendered (and translated) by the server;
            // CSS shows the one that matches, the tooltip copies it.
            const label = heart.querySelector(
                inWishlist ? ".o_g2b_wish_label_on" : ".o_g2b_wish_label_off"
            );
            if (label) {
                heart.title = label.textContent.trim();
            }
        };

        heart.addEventListener("click", (ev) => {
            ev.preventDefault();
            // Keep the click off the picture, which opens the zoom.
            ev.stopPropagation();
            if (!heart.classList.contains("o_g2b_wish_active")) {
                original.click();
            }
        });

        new MutationObserver(sync).observe(original, {
            attributes: true,
            attributeFilter: ["class", "disabled"],
        });
        sync();
    }

    function setup() {
        document.querySelectorAll(".o_wsale_product_page #o_wsale_cta_wrapper")
            .forEach(setupBuyForm);
        document.querySelectorAll(".o_wsale_product_page .o_g2b_wish_on_image")
            .forEach(setupWishlistHeart);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
