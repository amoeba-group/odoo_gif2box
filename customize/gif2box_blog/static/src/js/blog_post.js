/**
 * Blog post page: table of contents, reading progress, copy-link button.
 *
 * - The table of contents (`nav.o_g2b_toc`, `views/blog_templates.xml`) is
 *   filled from the post's own `h2` and `h3`, which get an id each so they
 *   can be linked to, from here and from search results. It only shows
 *   when there are at least two sections. Open on wide screens, folded on
 *   phones, where it would push the text a screen down.
 * - A thin bar along the top of the window shows how far through the post
 *   the reader is.
 * - "Copy link" copies the page's address and says so.
 *
 * Nothing runs in the website editor, where the post is being written.
 */

(function () {
    "use strict";

    function slugify(text, index) {
        var ascii = text
            .normalize("NFD")
            .replace(/[̀-ͯ]/g, "")
            .replace(/[đĐ]/g, "d")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 60);
        return ascii || "section-" + (index + 1);
    }

    function buildToc(content) {
        var nav = document.querySelector(".o_g2b_toc");
        var list = nav && nav.querySelector(".o_g2b_toc_list");
        if (!list) {
            return;
        }
        var headings = content.querySelectorAll("h2, h3");
        if (headings.length < 2) {
            return;
        }
        var used = {};
        headings.forEach(function (heading, index) {
            var text = heading.textContent.trim();
            if (!text) {
                return;
            }
            if (!heading.id) {
                var id = slugify(text, index);
                while (used[id] || document.getElementById(id)) {
                    id += "-" + (index + 1);
                }
                heading.id = id;
            }
            used[heading.id] = true;
            var item = document.createElement("li");
            item.className = "o_g2b_toc_item o_g2b_toc_" + heading.tagName.toLowerCase();
            var link = document.createElement("a");
            link.href = "#" + heading.id;
            link.textContent = text;
            item.append(link);
            list.append(item);
        });
        if (!list.children.length) {
            return;
        }
        var details = nav.querySelector("details");
        if (details && window.matchMedia("(max-width: 767.98px)").matches) {
            details.open = false;
        }
        nav.classList.remove("d-none");
    }

    function buildProgress(content) {
        var bar = document.createElement("div");
        bar.className = "o_g2b_read_progress";
        bar.setAttribute("aria-hidden", "true");
        document.body.append(bar);
        var frame = null;
        var update = function () {
            frame = null;
            var rect = content.getBoundingClientRect();
            var total = rect.height - window.innerHeight * 0.6;
            var done = total > 0 ? (-rect.top + window.innerHeight * 0.2) / total : 1;
            bar.style.transform = "scaleX(" + Math.min(1, Math.max(0, done)) + ")";
        };
        window.addEventListener("scroll", function () {
            if (!frame) {
                frame = requestAnimationFrame(update);
            }
        }, { passive: true });
        update();
    }

    function setupCopyLink() {
        var share = document.querySelector(".o_g2b_post_share");
        var button = share && share.querySelector(".o_g2b_copy_link");
        if (!button || !navigator.clipboard) {
            if (button) {
                button.remove();
            }
            return;
        }
        button.addEventListener("click", function () {
            navigator.clipboard.writeText(window.location.href.split("#")[0]).then(function () {
                share.classList.add("o_g2b_copied");
                setTimeout(function () {
                    share.classList.remove("o_g2b_copied");
                }, 2200);
            });
        });
    }

    function setup() {
        if (document.body.classList.contains("editor_enable")) {
            return;
        }
        var content = document.querySelector("#o_wblog_post_content .o_wblog_post_content_field");
        if (!content) {
            return;
        }
        buildToc(content);
        buildProgress(content);
        setupCopyLink();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
