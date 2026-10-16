/**
 * Product cards: have the second picture ready before the pointer arrives.
 *
 * Every card that has one carries it as `img.o_g2b_hover_img[data-src]`
 * (`views/product_card_templates.xml`). Fetched only on the first hover, it
 * arrived a beat after the pointer: the card zoomed on its first picture
 * and the crossfade came late, as a second movement. So, on screens with a
 * mouse, the picture is fetched as soon as its card is on screen, in idle
 * time, and the first hover is as smooth as the next. Hovering or focusing a
 * card still fetches it at once, in case the shopper got there first.
 *
 * The card is marked `o_g2b_hover_ready` only once the picture is decoded,
 * not merely downloaded: decoding a picture the moment it is first shown
 * costs a frame or two mid-fade, which is exactly the stutter to avoid.
 *
 * Touch screens cannot hover and get none of this; nor do visitors who asked
 * their browser to save data, except on an actual hover.
 *
 * Cards rendered later (the homepage rows, "alternative products") are
 * picked up as they appear.
 */

(function () {
    "use strict";

    var CARD = ".oe_product, .o_carousel_product_card";
    var PENDING = "img.o_g2b_hover_img[data-src]";

    var canHover = window.matchMedia
        && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    var saveData = navigator.connection && navigator.connection.saveData;

    function idle(fn) {
        if (window.requestIdleCallback) {
            window.requestIdleCallback(fn, { timeout: 2000 });
        } else {
            setTimeout(fn, 200);
        }
    }

    function prime(card) {
        if (!card || card.dataset.g2bHoverPrimed) {
            return;
        }
        var img = card.querySelector(PENDING);
        if (!img) {
            return;
        }
        card.dataset.g2bHoverPrimed = "1";
        var ready = function () {
            card.classList.add("o_g2b_hover_ready");
        };
        img.src = img.dataset.src;
        img.removeAttribute("data-src");
        if (img.decode) {
            img.decode().then(ready, function () {
                // `decode()` also rejects on a picture that did load but
                // could not be decoded ahead; only a real failure is left out.
                if (img.complete && img.naturalWidth) {
                    ready();
                }
            });
        } else {
            img.addEventListener("load", ready, { once: true });
        }
    }

    function cardOf(target) {
        return target && target.closest ? target.closest(CARD) : null;
    }

    // --- On screen: fetch ahead -----------------------------------------
    var observer = null;
    if (canHover && !saveData && window.IntersectionObserver) {
        observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    observer.unobserve(entry.target);
                    idle(function () {
                        prime(entry.target);
                    });
                }
            });
        }, { rootMargin: "200px 0px" });
    }

    function watch(root) {
        if (!observer) {
            return;
        }
        root.querySelectorAll(PENDING).forEach(function (img) {
            var card = cardOf(img);
            if (card && !card.dataset.g2bHoverWatched) {
                card.dataset.g2bHoverWatched = "1";
                observer.observe(card);
            }
        });
    }

    // --- On hover or focus: fetch now -----------------------------------
    // A mouse or a pen only: a finger's tap would fire this too, then
    // navigate before the picture could matter.
    document.addEventListener("pointerover", function (ev) {
        if (ev.pointerType === "mouse" || ev.pointerType === "pen") {
            prime(cardOf(ev.target));
        }
    }, { passive: true });

    document.addEventListener("focusin", function (ev) {
        prime(cardOf(ev.target));
    });

    function start() {
        watch(document);
        if (observer && window.MutationObserver) {
            var scheduled = false;
            new MutationObserver(function () {
                if (!scheduled) {
                    scheduled = true;
                    requestAnimationFrame(function () {
                        scheduled = false;
                        watch(document);
                    });
                }
            }).observe(document.body, { childList: true, subtree: true });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
