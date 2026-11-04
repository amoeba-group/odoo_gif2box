/**
 * The reviews on the product page (`views/product_review_templates.xml`):
 * filters (the chips and the bars per star), "Show more", "Read more" on
 * long reviews, and a viewer for the photos.
 *
 * Listeners on the document, so that the reviews fetched later behave as
 * the first ones; the next pages come as HTML from `/shop/reviews/<id>`.
 */
(function () {
    "use strict";

    // --- Read more ------------------------------------------------------------
    function foldLongReviews(root) {
        root.querySelectorAll(".o_g2b_rv_comment_wrap:not([data-g2b-folded])").forEach((wrap) => {
            wrap.dataset.g2bFolded = "1";
            const text = wrap.querySelector(".o_g2b_rv_comment");
            const button = wrap.querySelector(".o_g2b_rv_readmore");
            if (text && button && text.scrollHeight > text.clientHeight + 4) {
                button.classList.remove("d-none");
            }
        });
    }

    // --- Filters, more --------------------------------------------------------------
    async function load(section, kind, offset, append) {
        const list = section.querySelector(".o_g2b_rvs_list");
        list.setAttribute("aria-busy", "true");
        try {
            const url = `/shop/reviews/${section.dataset.productId}?kind=${encodeURIComponent(kind)}&offset=${offset}`;
            const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) {
                throw new Error(response.statusText);
            }
            const html = await response.text();
            if (append) {
                const more = list.querySelector(".o_g2b_rvs_more_wrap");
                if (more) {
                    more.remove();
                }
                list.insertAdjacentHTML("beforeend", html);
            } else {
                list.innerHTML = html;
            }
            foldLongReviews(list);
        } catch {
            // Leave the list as it was.
        } finally {
            list.setAttribute("aria-busy", "false");
        }
    }

    function setFilter(section, kind) {
        section.querySelectorAll(".o_g2b_rvs_filter").forEach((button) => {
            const on = button.dataset.kind === kind;
            button.classList.toggle("is-on", on);
            if (button.hasAttribute("aria-pressed")) {
                button.setAttribute("aria-pressed", on ? "true" : "false");
            }
        });
        section.dataset.kind = kind;
        load(section, kind, 0, false);
    }

    // --- Photo viewer ----------------------------------------------------------------
    let viewer = null;
    let gallery = [];
    let index = 0;
    let touchX = null;

    function buildViewer() {
        viewer = document.createElement("dialog");
        viewer.className = "o_g2b_lightbox";
        viewer.innerHTML = `
            <img class="o_g2b_lightbox_img" alt=""/>
            <button type="button" class="o_g2b_lightbox_btn o_g2b_lightbox_close" aria-label="×">×</button>
            <button type="button" class="o_g2b_lightbox_btn o_g2b_lightbox_prev" aria-label="‹">‹</button>
            <button type="button" class="o_g2b_lightbox_btn o_g2b_lightbox_next" aria-label="›">›</button>
            <div class="o_g2b_lightbox_count"></div>`;
        document.body.appendChild(viewer);
        viewer.querySelector(".o_g2b_lightbox_close").addEventListener("click", () => viewer.close());
        viewer.querySelector(".o_g2b_lightbox_prev").addEventListener("click", () => show(index - 1));
        viewer.querySelector(".o_g2b_lightbox_next").addEventListener("click", () => show(index + 1));
        viewer.addEventListener("click", (ev) => {
            if (ev.target === viewer) {
                viewer.close();
            }
        });
        viewer.addEventListener("keydown", (ev) => {
            if (ev.key === "ArrowLeft") {
                show(index - 1);
            } else if (ev.key === "ArrowRight") {
                show(index + 1);
            }
        });
        viewer.addEventListener("touchstart", (ev) => {
            touchX = ev.touches[0].clientX;
        }, { passive: true });
        viewer.addEventListener("touchend", (ev) => {
            if (touchX === null) {
                return;
            }
            const dx = ev.changedTouches[0].clientX - touchX;
            touchX = null;
            if (Math.abs(dx) > 40) {
                show(index + (dx < 0 ? 1 : -1));
            }
        });
    }

    function show(i) {
        index = (i + gallery.length) % gallery.length;
        viewer.querySelector(".o_g2b_lightbox_img").src = gallery[index];
        viewer.querySelector(".o_g2b_lightbox_count").textContent = gallery.length > 1 ? `${index + 1} / ${gallery.length}` : "";
        const several = gallery.length > 1;
        viewer.querySelector(".o_g2b_lightbox_prev").hidden = !several;
        viewer.querySelector(".o_g2b_lightbox_next").hidden = !several;
    }

    function openViewer(button) {
        const group = button.closest("[data-g2b-gallery]");
        const buttons = group ? [...group.querySelectorAll("[data-g2b-full]")] : [button];
        gallery = buttons.map((b) => b.dataset.g2bFull);
        if (!viewer) {
            buildViewer();
        }
        show(buttons.indexOf(button));
        if (viewer.showModal) {
            viewer.showModal();
        } else {
            window.open(gallery[index], "_blank");
        }
    }

    // --- Wiring -----------------------------------------------------------------------
    document.addEventListener("click", (ev) => {
        const filter = ev.target.closest(".o_g2b_rvs_filter");
        if (filter && !filter.disabled) {
            const section = filter.closest(".o_g2b_rvs");
            const kind = filter.classList.contains("is-on") && filter.dataset.kind !== "all" ? "all" : filter.dataset.kind;
            setFilter(section, kind);
            if (filter.classList.contains("o_g2b_rvs_bar")) {
                section.querySelector(".o_g2b_rvs_main").scrollIntoView({ behavior: "smooth", block: "start" });
            }
            return;
        }
        const more = ev.target.closest(".o_g2b_rvs_more");
        if (more) {
            const section = more.closest(".o_g2b_rvs");
            more.disabled = true;
            load(section, more.dataset.kind || "all", more.dataset.next || 0, true);
            return;
        }
        const readMore = ev.target.closest(".o_g2b_rv_readmore");
        if (readMore) {
            readMore.closest(".o_g2b_rv_comment_wrap").classList.toggle("is-open");
            return;
        }
        const photo = ev.target.closest("[data-g2b-full]");
        if (photo) {
            ev.preventDefault();
            openViewer(photo);
        }
    });

    function start() {
        document.querySelectorAll(".o_g2b_rvs").forEach(foldLongReviews);
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
