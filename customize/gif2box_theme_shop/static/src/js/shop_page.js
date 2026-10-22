/**
 * The shop, category and search listing (`views/shop_templates.xml`).
 *
 * - The category's introduction is folded to a few lines, with "Read
 *   more", once it is long enough to push the products off the first
 *   screen. Only running text: a header the client built from blocks
 *   (banners, columns) is a layout, and stays as laid out.
 *
 * - "Show more products" appends the next page to the grid instead of
 *   opening it. The button is a plain link to that page, so without this
 *   script, and for search engines, it is ordinary paging. After a load the
 *   address asks for as many products as are on screen (`?ppg=40`), so
 *   going back from a product returns to the same list, at the same place,
 *   rather than to the first twenty. The new cards need nothing started:
 *   the cart and wishlist buttons are handled at the page level, and the
 *   hover pictures pick up new cards by themselves.
 *
 * - Chip rows that scroll sideways (phones) start with the selected chip in
 *   view, and fade at the side that has more.
 *
 * Nothing runs in the website editor: the folded text would hide what is
 * being edited, and a click there means "select", not "go".
 */

(function () {
    "use strict";

    function editing() {
        return document.body.classList.contains("editor_enable");
    }

    // --- Introduction ----------------------------------------------------
    function setupIntro() {
        var intro = document.querySelector(".o_g2b_shop_intro");
        var body = intro && intro.querySelector("#category_header");
        var toggle = intro && intro.querySelector(".o_g2b_shop_intro_toggle");
        if (!body || !toggle || !body.textContent.trim()
            || body.querySelector("section, iframe, video")) {
            return;
        }

        function measure() {
            if (intro.classList.contains("o_g2b_open")) {
                return;
            }
            intro.classList.add("o_g2b_folded");
            // A few pixels of slack: a last line's descenders are not
            // worth a button.
            var overflows = body.scrollHeight - body.clientHeight > 6;
            intro.classList.toggle("o_g2b_folded", overflows);
            toggle.classList.toggle("d-none", !overflows);
        }

        toggle.addEventListener("click", function () {
            var open = intro.classList.toggle("o_g2b_open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });

        measure();
        var timer = null;
        window.addEventListener("resize", function () {
            clearTimeout(timer);
            timer = setTimeout(measure, 150);
        }, { passive: true });
    }

    // --- Chip rows -------------------------------------------------------
    function setupChipRows() {
        document.querySelectorAll(".o_g2b_chip_row").forEach(function (row) {
            function edges() {
                var max = row.scrollWidth - row.clientWidth;
                row.classList.toggle("o_g2b_more_start", row.scrollLeft > 2);
                row.classList.toggle("o_g2b_more_end", max - row.scrollLeft > 2);
            }
            var active = row.querySelector(".o_g2b_chip.active");
            if (active && active.offsetLeft + active.offsetWidth > row.clientWidth) {
                row.scrollLeft = active.offsetLeft - 16;
            }
            edges();
            row.addEventListener("scroll", edges, { passive: true });
            window.addEventListener("resize", edges, { passive: true });
        });
    }

    // --- Show more products ----------------------------------------------
    var startPage = null;

    function remember(shown) {
        // Only from the first page: a visit that began on page 3 has no
        // first forty products on screen to come back to.
        if (startPage !== 1 || !shown || !window.history.replaceState) {
            return;
        }
        var url = new URL(window.location.href);
        url.searchParams.set("ppg", shown);
        window.history.replaceState(window.history.state, "",
            url.pathname + url.search + url.hash);
    }

    function announce(block) {
        var status = document.getElementById("o_g2b_more_status");
        if (!status || !block) {
            return;
        }
        var loaded = block.querySelector(".o_g2b_more_loaded_msg");
        var count = block.querySelector(".o_g2b_more_count");
        status.textContent = [loaded, count]
            .filter(Boolean)
            .map(function (el) { return el.textContent.replace(/\s+/g, " ").trim(); })
            .join(". ");
    }

    function loadMore(btn) {
        var grid = document.getElementById("o_wsale_products_grid");
        var block = btn.closest(".o_g2b_more");
        if (!grid || !block || !window.fetch || !window.DOMParser) {
            window.location.href = btn.href;
            return;
        }
        if (btn.getAttribute("aria-busy") === "true") {
            return;
        }
        btn.setAttribute("aria-busy", "true");
        btn.classList.add("o_g2b_loading");

        fetch(btn.href, { credentials: "same-origin" })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error(String(response.status));
                }
                return response.text();
            })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, "text/html");
                var cards = doc.querySelectorAll("#o_wsale_products_grid > .oe_product");
                if (!cards.length) {
                    throw new Error("no products");
                }
                var first = null;
                cards.forEach(function (card) {
                    var node = document.importNode(card, true);
                    grid.appendChild(node);
                    first = first || node;
                });

                var next = doc.querySelector(".o_g2b_more");
                var current = next ? document.importNode(next, true) : null;
                if (current) {
                    block.replaceWith(current);
                } else {
                    block.remove();
                }
                var shown = current && current.querySelector(".o_g2b_more_shown");
                remember(shown ? parseInt(shown.textContent, 10) : 0);
                announce(current);

                // Keyboard and screen reader users carry on from the first
                // new product rather than from a button that may be gone.
                var link = first.querySelector(".o_wsale_products_item_title a")
                    || first.querySelector("a[href]");
                if (link) {
                    link.focus({ preventScroll: true });
                }
            })
            .catch(function () {
                // Whatever went wrong, the page itself is one click away.
                window.location.href = btn.href;
            });
    }

    function setupMore() {
        var block = document.querySelector(".o_g2b_more");
        startPage = block ? parseInt(block.dataset.g2bPage, 10) : null;

        document.addEventListener("click", function (ev) {
            var btn = ev.target.closest && ev.target.closest(".o_g2b_more_btn");
            // A modified click is a request for a new tab: leave it be.
            if (!btn || ev.defaultPrevented || ev.button !== 0
                || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey || editing()) {
                return;
            }
            ev.preventDefault();
            loadMore(btn);
        });
    }

    function start() {
        if (!document.querySelector(".o_wsale_products_page") || editing()) {
            return;
        }
        setupIntro();
        setupChipRows();
        setupMore();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
