/**
 * Product cards: fetch the second picture when the pointer first comes on.
 *
 * Every card that has one carries it as `img.o_g2b_hover_img[data-src]`
 * (`views/product_card_templates.xml`). It is only fetched on the first
 * hover, or keyboard focus, of its card, so a grid of cards costs what it
 * did; the card is marked `o_g2b_hover_ready` once the picture has fully
 * arrived, and only then does the stylesheet crossfade to it, so a slow
 * picture never shows as an empty frame.
 *
 * Listened for on the document, not on each card: the homepage rows and the
 * "alternative products" are rendered by scripts after the page has loaded.
 */

(function () {
    "use strict";

    var CARD = ".oe_product, .o_carousel_product_card";

    function prime(target) {
        var card = target && target.closest ? target.closest(CARD) : null;
        if (!card || card.dataset.g2bHoverPrimed) {
            return;
        }
        card.dataset.g2bHoverPrimed = "1";
        var img = card.querySelector("img.o_g2b_hover_img[data-src]");
        if (!img) {
            return;
        }
        img.addEventListener("load", function () {
            card.classList.add("o_g2b_hover_ready");
        }, { once: true });
        img.src = img.dataset.src;
        img.removeAttribute("data-src");
    }

    // A mouse or a pen only: a finger's tap would fire this too, then
    // navigate before the picture could matter.
    document.addEventListener("pointerover", function (ev) {
        if (ev.pointerType === "mouse" || ev.pointerType === "pen") {
            prime(ev.target);
        }
    }, { passive: true });

    document.addEventListener("focusin", function (ev) {
        prime(ev.target);
    });
})();
