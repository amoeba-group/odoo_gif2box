/** @odoo-module **/

/**
 * The homepage's product sections: Gift Box as a sliding rail, Life as a grid.
 *
 * Both are Odoo's "Products" snippet, so the client still picks the category
 * and the number of products in the website editor. They are marked
 * `.o_g2b_home_products` in the page, plus `.o_g2b_home_rail` for the one that
 * slides; `home_sections.scss` lays them out.
 *
 * The snippet pages its products through a Bootstrap carousel, four at a time.
 * Here every product goes on a single slide instead, so the stylesheet can
 * turn that one row into a native scroll track (rail) or a CSS grid. A
 * scroll track is what phones expect, swiped and with the next card peeking
 * in, and it moves a card at a time rather than a page.
 *
 * Sold-out products are left out of both rows; see `_getRpcParameters`.
 *
 * The rail adds, below the products:
 * - previous / next arrows for a mouse, hidden when there is nothing to scroll;
 * - a closing "View all" card, worded like the section's own header link;
 * - an unhurried auto-advance. It stops for good the moment the shopper
 *   touches the rail, and pauses while the pointer or the focus is on it,
 *   while it is off screen or the tab is hidden; it never starts in the
 *   editor, nor for visitors who ask for reduced motion.
 *
 * Everything added lives inside the snippet's `.dynamic_snippet_template`,
 * which Odoo empties on every render and before saving, so none of it can end
 * up in the page's stored content.
 */

import { _t } from "@web/core/l10n/translation";
import DynamicSnippet from "@website/snippets/s_dynamic_snippet/000";

const AUTOPLAY_DELAY = 5000;

class ProductRail {
    constructor(section, { autoplay }) {
        this.section = section;
        this.track = section.querySelector(".dynamic_snippet_template .s_dynamic_snippet_row");
        this.carousel = section.querySelector(".dynamic_snippet_template .carousel");
        if (!this.track || !this.carousel) {
            return;
        }
        this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        this.cleanups = [];

        this._addClosingCard();
        this._addArrows();

        this._listen(this.track, "scroll", () => this._scheduleUpdate(), { passive: true });
        if (window.ResizeObserver) {
            const observer = new ResizeObserver(() => this._scheduleUpdate());
            observer.observe(this.track);
            this.cleanups.push(() => observer.disconnect());
        }
        this._update();

        if (autoplay && !this.reducedMotion) {
            this._setupAutoplay();
        }
    }

    destroy() {
        this._stopAutoplay();
        for (const cleanup of this.cleanups || []) {
            cleanup();
        }
        this.cleanups = [];
    }

    // -------------------------------------------------------------------------
    // Building
    // -------------------------------------------------------------------------

    _addClosingCard() {
        const headerLink = this.section.closest(".o_g2b_home_section")?.querySelector(".o_g2b_sec_all");
        if (!headerLink) {
            return;
        }
        const item = document.createElement("div");
        item.className = "o_g2b_rail_more";
        const link = document.createElement("a");
        link.className = "o_g2b_rail_more_link";
        link.href = headerLink.href;
        const icon = document.createElement("span");
        icon.className = "o_g2b_rail_more_icon";
        icon.setAttribute("aria-hidden", "true");
        icon.innerHTML = '<i class="fa fa-arrow-right"></i>';
        const label = document.createElement("span");
        label.className = "o_g2b_rail_more_label";
        // The header link's own words, already in the visitor's language.
        label.textContent = headerLink.textContent.trim();
        link.append(icon, label);
        if (headerLink.getAttribute("aria-label")) {
            link.setAttribute("aria-label", headerLink.getAttribute("aria-label"));
        }
        item.append(link);
        this.track.append(item);
    }

    _addArrows() {
        const make = (direction, label) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `o_g2b_rail_arrow o_g2b_rail_arrow_${direction}`;
            button.setAttribute("aria-label", label);
            button.title = label;
            button.innerHTML = `<i class="fa fa-chevron-${direction === "prev" ? "left" : "right"}" aria-hidden="true"></i>`;
            this._listen(button, "click", () => {
                this._stopAutoplay(true);
                this._page(direction === "prev" ? -1 : 1);
            });
            this.carousel.append(button);
            return button;
        };
        this.prevButton = make("prev", _t("Previous"));
        this.nextButton = make("next", _t("Next"));
    }

    // -------------------------------------------------------------------------
    // Moving
    // -------------------------------------------------------------------------

    _step() {
        const first = this.track.firstElementChild;
        if (!first) {
            return this.track.clientWidth;
        }
        const gap = parseFloat(getComputedStyle(this.track).columnGap) || 0;
        return first.getBoundingClientRect().width + gap;
    }

    _scrollTo(left) {
        this.track.scrollTo({ left, behavior: this.reducedMotion ? "auto" : "smooth" });
    }

    /** As many whole cards as fit, so a click never cuts a card in half. */
    _page(direction) {
        const step = this._step();
        const perPage = Math.max(1, Math.floor((this.track.clientWidth + 1) / step));
        this._scrollTo(this.track.scrollLeft + direction * perPage * step);
    }

    _atStart() {
        return this.track.scrollLeft <= 2;
    }

    _atEnd() {
        return this.track.scrollLeft + this.track.clientWidth >= this.track.scrollWidth - 2;
    }

    _scheduleUpdate() {
        if (this.frame) {
            return;
        }
        this.frame = requestAnimationFrame(() => {
            this.frame = null;
            this._update();
        });
    }

    _update() {
        const scrollable = this.track.scrollWidth > this.track.clientWidth + 2;
        this.section.classList.toggle("o_g2b_rail_static", !scrollable);
        this.prevButton.disabled = !scrollable || this._atStart();
        this.nextButton.disabled = !scrollable || this._atEnd();
    }

    // -------------------------------------------------------------------------
    // Auto-advance
    // -------------------------------------------------------------------------

    _setupAutoplay() {
        this.paused = new Set();
        const pause = (reason) => () => {
            this.paused.add(reason);
            this._restartTimer();
        };
        const resume = (reason) => () => {
            this.paused.delete(reason);
            this._restartTimer();
        };

        this._listen(this.section, "mouseenter", pause("hover"));
        this._listen(this.section, "mouseleave", resume("hover"));
        this._listen(this.section, "focusin", pause("focus"));
        this._listen(this.section, "focusout", resume("focus"));
        // Any hand on the rail means the shopper is in charge from now on.
        for (const type of ["pointerdown", "wheel", "touchstart", "keydown"]) {
            this._listen(this.track, type, () => this._stopAutoplay(true), { passive: true });
        }
        this._listen(document, "visibilitychange", () => {
            (document.hidden ? pause : resume)("hidden")();
        });
        if (window.IntersectionObserver) {
            const observer = new IntersectionObserver(([entry]) => {
                (entry.isIntersecting ? resume : pause)("offscreen")();
            }, { threshold: 0.35 });
            observer.observe(this.section);
            this.cleanups.push(() => observer.disconnect());
            this.paused.add("offscreen");
        }
        this._restartTimer();
    }

    _restartTimer() {
        clearTimeout(this.timer);
        if (this.stopped || !this.paused || this.paused.size) {
            return;
        }
        this.timer = setTimeout(() => {
            if (this._atEnd()) {
                this._scrollTo(0);
            } else {
                this._scrollTo(this.track.scrollLeft + this._step());
            }
            this._restartTimer();
        }, AUTOPLAY_DELAY);
    }

    _stopAutoplay(forGood = false) {
        clearTimeout(this.timer);
        if (forGood) {
            this.stopped = true;
        }
    }

    _listen(target, type, handler, options) {
        target.addEventListener(type, handler, options);
        this.cleanups.push(() => target.removeEventListener(type, handler, options));
    }
}

DynamicSnippet.include({
    /**
     * In-stock products only: these rows are there to sell. The server fills
     * the row past the sold-out ones (`models/website_snippet_filter.py`).
     *
     * @override
     */
    _getRpcParameters() {
        const params = this._super(...arguments);
        if (this.el.classList.contains("o_g2b_home_products")) {
            params.gif2box_hide_sold_out = true;
        }
        return params;
    },

    /**
     * Every product on one slide; the stylesheet does the layout.
     *
     * @override
     */
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        if (this.el.classList.contains("o_g2b_home_products")) {
            // One row: the carousel's "rows per slide" defaults to 1 and is
            // not set on these snippets.
            options.chunkSize = Math.max(1, parseInt(this.el.dataset.numberOfRecords, 10) || 1);
        }
        return options;
    },

    /**
     * @override
     */
    _renderContent() {
        this._g2bRail?.destroy();
        this._g2bRail = null;
        this._super(...arguments);
        if (this.el.classList.contains("o_g2b_home_rail") && this.data?.length) {
            this._g2bRail = new ProductRail(this.el, { autoplay: !this.editableMode });
        }
    },

    /**
     * @override
     */
    destroy() {
        this._g2bRail?.destroy();
        this._g2bRail = null;
        this._super(...arguments);
    },
});
