/**
 * Holds the page loader until the page is genuinely usable.
 *
 * `window.load` is not enough on the homepage: the product rows come from
 * dynamic snippets that Odoo fills over RPC afterwards, so the overlay used to
 * lift onto empty placeholders. The overlay now waits for every dynamic
 * snippet on the page to have rendered its cards, and for those cards' images
 * to have decoded.
 *
 * Two escape hatches keep a stalled request from leaving the site hidden: the
 * image wait is capped, and a hard timeout clears the overlay regardless.
 */
(function () {
    "use strict";

    var HARD_TIMEOUT_MS = 10000;
    var IMAGE_WAIT_MS = 2500;
    var POLL_MS = 100;

    var done = false;

    function hideLoader() {
        if (done) {
            return;
        }
        done = true;
        var loader = document.getElementById("gif2box_loader");
        if (!loader) {
            return;
        }
        loader.classList.add("o_gif2box_loader_done");
        window.setTimeout(function () {
            if (loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
        }, 400);
    }

    function holders() {
        return document.querySelectorAll(".s_dynamic .dynamic_snippet_template");
    }

    /** True when every dynamic snippet has put something in its container. */
    function snippetsRendered() {
        var list = holders();
        if (!list.length) {
            return true;
        }
        return Array.prototype.every.call(list, function (el) {
            return el.children.length > 0;
        });
    }

    function imagesSettled() {
        var imgs = document.querySelectorAll(
            ".s_dynamic .dynamic_snippet_template img"
        );
        return Array.prototype.every.call(imgs, function (img) {
            return img.complete;
        });
    }

    /** Poll for the images, giving up after IMAGE_WAIT_MS. */
    function waitForImages(cb) {
        var waited = 0;
        (function poll() {
            if (done || imagesSettled() || waited >= IMAGE_WAIT_MS) {
                cb();
                return;
            }
            waited += POLL_MS;
            window.setTimeout(poll, POLL_MS);
        })();
    }

    function waitForSnippets(cb) {
        if (snippetsRendered()) {
            cb();
            return;
        }
        var observer = new MutationObserver(function () {
            if (snippetsRendered()) {
                observer.disconnect();
                cb();
            }
        });
        var sections = document.querySelectorAll(".s_dynamic");
        Array.prototype.forEach.call(sections, function (section) {
            observer.observe(section, {childList: true, subtree: true});
        });
        // The observer is dropped by the hard timeout below if it never fires.
        window.setTimeout(function () {
            observer.disconnect();
        }, HARD_TIMEOUT_MS);
    }

    function start() {
        waitForSnippets(function () {
            waitForImages(hideLoader);
        });
    }

    if (document.readyState === "complete") {
        start();
    } else {
        window.addEventListener("load", start);
    }

    window.setTimeout(hideLoader, HARD_TIMEOUT_MS);
})();
