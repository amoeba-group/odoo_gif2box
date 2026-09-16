/**
 * Folds a long product description behind a "Read more" button.
 *
 * `views/product_templates.xml` moves the description below the image and the
 * buy panel. That fixes the buy button being thousands of pixels down the
 * page, but the description itself is still a dozen full-width images, so the
 * page stays very long and everything under it -- the footer, the recommended
 * products -- is effectively out of reach. Folding it gives the shopper the
 * first screenful and a way to ask for the rest.
 *
 * Height cannot be measured on DOMContentLoaded: the images carry no width or
 * height attributes and are lazily loaded, so the block measures near zero
 * until they arrive. The fold is therefore applied up front on a cheap proxy
 * (how much content there is), and corrected once the real height is known.
 */

(function () {
    "use strict";

    // Roughly one screenful. Matches the `max-height` in `product_page.scss`;
    // the check runs a little over it so a description that only just exceeds
    // the fold is left alone rather than folded to save 40 pixels.
    const FOLD_AT = 780;

    function setup() {
        const body = document.querySelector(".o_g2b_pd_body");
        const wrap = document.querySelector(".o_g2b_pd_more_wrap");
        if (!body || !wrap) {
            return;
        }
        const button = wrap.querySelector(".o_g2b_pd_more");
        if (!button) {
            return;
        }

        let expanded = false;

        const fold = () => {
            body.classList.add("o_g2b_pd_clamped");
            wrap.classList.remove("d-none");
        };

        const unfold = () => {
            body.classList.remove("o_g2b_pd_clamped");
            wrap.classList.add("d-none");
        };

        // Before the images have loaded, the amount of markup is the only
        // signal available. A description of several images or a few hundred
        // characters is always taller than the fold once it renders.
        if (body.querySelectorAll("img").length > 1
                || body.textContent.trim().length > 600) {
            fold();
        }

        // Once heights are real, either confirm the fold or drop it.
        const recheck = () => {
            if (expanded) {
                return;
            }
            const height = body.classList.contains("o_g2b_pd_clamped")
                ? body.scrollHeight
                : body.getBoundingClientRect().height;
            if (height > FOLD_AT) {
                fold();
            } else {
                unfold();
            }
        };

        button.addEventListener("click", () => {
            expanded = !expanded;
            button.classList.toggle("o_g2b_pd_expanded", expanded);
            if (expanded) {
                body.classList.remove("o_g2b_pd_clamped");
            } else {
                body.classList.add("o_g2b_pd_clamped");
                // Folding from halfway down the description would otherwise
                // drop the reader somewhere below the whole section.
                const top = body.getBoundingClientRect().top + window.scrollY;
                window.scrollTo({ top: top - 120, behavior: "smooth" });
            }
        });

        window.addEventListener("load", recheck);
        if (window.ResizeObserver) {
            // Images arrive one by one; the observer catches each reflow.
            new ResizeObserver(recheck).observe(body);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
