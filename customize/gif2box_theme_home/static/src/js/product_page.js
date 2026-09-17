/**
 * Folds long blocks on the product page behind a "Read more" button.
 *
 * Two of them:
 *
 * - the description moved below the buy panel by `views/product_templates.xml`,
 *   which is a dozen full-width marketing images;
 * - the sales description inside the "More Information" accordion, which on
 *   this catalogue runs to twenty lines of specifications and policy.
 *
 * Any element with `.o_g2b_fold` holding a `.o_g2b_pd_body` and a
 * `.o_g2b_pd_more_wrap` is picked up. `data-fold-at` sets the height, in
 * pixels, above which folding is worth doing; it should match the
 * `max-height` the matching CSS rule applies.
 *
 * Height cannot be measured on DOMContentLoaded: images carry no width or
 * height attributes and are lazily loaded, so a block measures near zero
 * until they arrive. The fold is therefore applied up front on a cheap proxy
 * (how much content there is), and corrected once the real height is known.
 */

(function () {
    "use strict";

    const DEFAULT_FOLD_AT = 780;

    function setupFold(root) {
        const body = root.querySelector(".o_g2b_pd_body");
        const wrap = root.querySelector(".o_g2b_pd_more_wrap");
        if (!body || !wrap) {
            return;
        }
        const button = wrap.querySelector(".o_g2b_pd_more");
        if (!button) {
            return;
        }

        const foldAt = parseInt(root.dataset.foldAt, 10) || DEFAULT_FOLD_AT;
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
        // signal available. A block of several images, or of a few hundred
        // characters, is always taller than the fold once it renders.
        if (body.querySelectorAll("img").length > 1
                || body.textContent.trim().length > foldAt) {
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
            if (height > foldAt) {
                fold();
            } else {
                unfold();
            }
        };

        button.addEventListener("click", () => {
            expanded = !expanded;
            // On the root, not the button: the open state has to reach the
            // button's wrapper as well, which sits above it in the tree.
            root.classList.toggle("o_g2b_fold_open", expanded);
            if (expanded) {
                body.classList.remove("o_g2b_pd_clamped");
            } else {
                body.classList.add("o_g2b_pd_clamped");
                // Folding from halfway down would otherwise drop the reader
                // somewhere below the whole block.
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

    function setup() {
        document.querySelectorAll(".o_g2b_fold").forEach(setupFold);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
