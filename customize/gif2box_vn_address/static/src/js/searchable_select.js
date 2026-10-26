/** @odoo-module **/
/**
 * Searchable dropdowns for the address forms: province, ward, country.
 *
 * A native <select> of 34 provinces, 168 wards or 250 countries is a long
 * scroll, worst on a phone. Every `select[data-g2b-searchable]` gets a
 * picker with a search box instead:
 *
 * - typing filters as you go, by the beginnings of words and without the
 *   accents ("ben thanh" finds "Phường Bến Thành", "binh duong" the
 *   province it is part of now, through the option's `data-g2b-keywords`),
 *   the matched letters in bold, names that start with the words first;
 * - arrows, Enter and Escape work as in a native list, and typing on the
 *   closed field opens it with that letter already searched;
 * - on a phone it opens full screen, search on top, so the keyboard does
 *   not cover the list.
 *
 * The <select> stays where it is, in the form, and is still what is
 * submitted, read and validated; the picker is only put after it. Where it
 * is matters: Odoo's address script shows, hides and labels a field through
 * the select's parent and its `label[for]`, and the portal hides the
 * province the same way. It is made invisible but kept laid out, at the
 * foot of the field: Odoo checks the form with `reportValidity()`, and the
 * browser can only point at a missing field it can place on the page.
 *
 * A choice is written to it with a `change` event, so the scripts already
 * listening (Odoo's address form, the ward loader, the portal's country
 * filter) run as before; and the picker follows the select back: options
 * replaced, disabled, hidden, marked invalid.
 *
 * Options marked `d-none`, `hidden` or `disabled` are left out, which is how
 * the portal hides the provinces of other countries.
 */
import { _t } from "@web/core/l10n/translation";

const SELECTOR = "select[data-g2b-searchable]";
const PHONE = window.matchMedia("(max-width: 767.98px)");
// Dropped before ranking, so that "ben" ranks "Phường Bến Thành" first.
const PREFIX = /^(thành phố|tỉnh|tp\.?|phường|xã|đặc khu)\s+/i;
let uid = 0;

// --- Matching --------------------------------------------------------------

/**
 * `text` without accents, in lower case, with the index in `text` of every
 * character kept, to put the highlight back on the original.
 */
function fold(text) {
    const chars = [];
    const map = [];
    for (let i = 0; i < text.length; i++) {
        const base = text[i]
            .normalize("NFD")
            .replace(/[̀-ͯ]/g, "")
            .replace(/[đĐ]/g, "d")
            .toLowerCase();
        for (const ch of base) {
            chars.push(ch);
            map.push(i);
        }
    }
    return { folded: chars.join(""), map };
}

function foldWords(text) {
    return fold(text).folded.split(/\s+/).filter(Boolean);
}

/** The words of a folded text, with where each starts. */
function tokens(folded) {
    const found = [];
    const re = /[^\s\-,.()/]+/g;
    let m;
    while ((m = re.exec(folded))) {
        found.push({ start: m.index, text: m[0] });
    }
    return found;
}

/**
 * Whether `item` matches the query, and how well; null for no match.
 *
 * Every word typed must begin a word of the option's name or of its
 * keywords: "ben thanh" finds "Phường Bến Thành", "han quoc" finds South
 * Korea by its keywords, and neither finds "Thành quốc Vatican", whose
 * "thanh" merely contains "han". Best first: the name (prefix aside)
 * starting with the query, then every word found in the name itself, then
 * matches on keywords only. A province merged away comes after all of them.
 */
function rank(item, words, query) {
    let score = 2;
    if (words.length) {
        let inName = true;
        for (const word of words) {
            const name = item.tokens.some((t) => t.text.startsWith(word));
            if (!name && !item.keywordTokens.some((t) => t.startsWith(word))) {
                return null;
            }
            inName &&= name;
        }
        score = item.bare.startsWith(query) ? 0 : inName ? 1 : 2;
    }
    return item.obsolete ? score + 10 : score;
}

/** The option's name, with the matched word beginnings in <mark>. */
function highlight(item, words) {
    const ranges = [];
    for (const word of words) {
        const token = item.tokens.find((t) => t.text.startsWith(word));
        if (token) {
            const end = token.start + word.length - 1;
            ranges.push([item.label.map[token.start], item.label.map[end] + 1]);
        }
    }
    ranges.sort((a, b) => a[0] - b[0]);
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    for (const [start, end] of ranges) {
        if (start < cursor) {
            continue;
        }
        fragment.append(item.text.slice(cursor, start));
        const mark = document.createElement("mark");
        mark.textContent = item.text.slice(start, end);
        fragment.append(mark);
        cursor = end;
    }
    fragment.append(item.text.slice(cursor));
    return fragment;
}

// --- The picker ------------------------------------------------------------

class SearchableSelect {
    constructor(select) {
        this.select = select;
        this.id = `o_g2b_ss_${++uid}`;
        this.active = -1;
        this.results = [];
        select.dataset.g2bSsReady = "1";

        this.host = select.parentElement;
        this.host.classList.add("o_g2b_ss_host");
        select.classList.add("o_g2b_ss_native");
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");

        this.trigger = document.createElement("button");
        this.trigger.type = "button";
        this.trigger.className = "form-select o_g2b_ss_trigger";
        this.trigger.setAttribute("aria-haspopup", "listbox");
        this.trigger.setAttribute("aria-expanded", "false");
        this.value = document.createElement("span");
        this.value.className = "o_g2b_ss_value";
        this.trigger.append(this.value);
        select.after(this.trigger);

        // The field's label names the picker. It keeps pointing at the
        // select, which Odoo relies on; a click on it focuses the select,
        // and the focus is passed on (below).
        const label = select.id && document.querySelector(`label[for="${select.id}"]`);
        this.title = (label?.textContent || select.getAttribute("aria-label") || "")
            .replace(/\*/g, "").trim();
        if (label) {
            label.id ||= `${this.id}_label`;
            this.trigger.setAttribute("aria-labelledby", `${label.id} ${this.id}_value`);
            this.value.id = `${this.id}_value`;
        }

        this.trigger.addEventListener("click", () => (this.isOpen ? this.close() : this.open()));
        this.trigger.addEventListener("keydown", (ev) => this._onTriggerKeydown(ev));
        select.addEventListener("change", () => this.sync());
        select.addEventListener("invalid", () => {
            this.trigger.classList.add("is-invalid");
            this._invalidAt = Date.now();
        });
        // A click on the label lands on the select: on to the picker. Not
        // when the browser is pointing at the field as missing, though:
        // moving the focus would take its message away.
        select.addEventListener("focus", () => {
            if (Date.now() - (this._invalidAt || 0) > 300) {
                this.trigger.focus();
            }
        });
        new MutationObserver(() => this.sync()).observe(select, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["disabled", "class", "hidden", "style"],
        });
        this.sync();
    }

    get isOpen() {
        return this.trigger.getAttribute("aria-expanded") === "true";
    }

    /** The options to offer, with their folded forms (cached). */
    items() {
        this._cache ||= new WeakMap();
        const items = [];
        for (const option of this.select.options) {
            if (!option.value || option.disabled || option.hidden
                || option.classList.contains("d-none") || option.style.display === "none") {
                continue;
            }
            let item = this._cache.get(option);
            const text = option.textContent.replace(/\s+/g, " ").trim();
            if (!item || item.text !== text) {
                const label = fold(text);
                item = {
                    value: option.value,
                    text,
                    label,
                    tokens: tokens(label.folded),
                    bare: fold(text.replace(PREFIX, "")).folded,
                    keywordTokens: tokens(fold(option.dataset.g2bKeywords || "").folded)
                        .map((t) => t.text),
                    hint: option.dataset.g2bHint || "",
                    obsolete: !!option.dataset.g2bObsolete,
                };
                this._cache.set(option, item);
            }
            items.push(item);
        }
        return items;
    }

    /** The field as the select says it is. */
    sync() {
        const select = this.select;
        const chosen = select.selectedOptions[0];
        const placeholder = [...select.options].find((o) => !o.value);
        this.trigger.disabled = select.disabled;
        this.trigger.classList.toggle("is-invalid", select.classList.contains("is-invalid"));
        this.trigger.classList.toggle("o_g2b_ss_placeholder", !select.value);
        this.value.textContent = (select.value ? chosen?.textContent : placeholder?.textContent || "")
            ?.replace(/\s+/g, " ").trim() || "";
        if (select.disabled && this.isOpen) {
            this.close(false);
        } else if (this.isOpen) {
            this.render();
        }
    }

    _build() {
        const panel = document.createElement("div");
        panel.className = "o_g2b_ss_panel";
        panel.innerHTML = `
            <div class="o_g2b_ss_head">
                <span class="o_g2b_ss_title"></span>
                <button type="button" class="o_g2b_ss_close">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
                         stroke-linecap="round" aria-hidden="true" focusable="false">
                        <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
                    </svg>
                </button>
            </div>
            <div class="o_g2b_ss_search">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" aria-hidden="true" focusable="false">
                    <circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>
                </svg>
                <input type="text" class="o_g2b_ss_input" role="combobox"
                       aria-autocomplete="list" aria-expanded="true"
                       autocomplete="off" autocapitalize="off" spellcheck="false"/>
            </div>
            <ul class="o_g2b_ss_list" role="listbox"></ul>
            <p class="o_g2b_ss_empty" hidden></p>`;
        panel.querySelector(".o_g2b_ss_title").textContent = this.title;
        const close = panel.querySelector(".o_g2b_ss_close");
        close.setAttribute("aria-label", _t("Close"));
        close.addEventListener("click", () => this.close());

        this.input = panel.querySelector(".o_g2b_ss_input");
        this.list = panel.querySelector(".o_g2b_ss_list");
        this.empty = panel.querySelector(".o_g2b_ss_empty");
        this.list.id = `${this.id}_list`;
        this.list.setAttribute("aria-label", this.title);
        this.input.setAttribute("aria-controls", this.list.id);
        this.input.setAttribute("aria-label", this.title);
        this.input.placeholder = this.select.getAttribute("placeholder") || _t("Search...");
        this.input.addEventListener("input", () => {
            this.active = 0;
            this.render();
        });
        this.input.addEventListener("keydown", (ev) => this._onInputKeydown(ev));

        // Pressing an option must not take the focus off the search box,
        // or the panel would close before the click lands.
        this.list.addEventListener("mousedown", (ev) => ev.preventDefault());
        this.list.addEventListener("click", (ev) => {
            const li = ev.target.closest("[role=option]");
            if (li) {
                this.choose(li.dataset.value);
            }
        });
        this.list.addEventListener("mousemove", (ev) => {
            const li = ev.target.closest("[role=option]");
            if (li && Number(li.dataset.index) !== this.active) {
                this._setActive(Number(li.dataset.index), false);
            }
        });
        this.panel = panel;
    }

    open(query = "") {
        if (this.select.disabled || this.isOpen) {
            return;
        }
        if (!this.panel) {
            this._build();
        }
        this.sheet = PHONE.matches;
        this.panel.classList.toggle("o_g2b_ss_sheet", this.sheet);
        this.panel.classList.remove("o_g2b_ss_up");
        if (this.sheet) {
            document.body.append(this.panel);
        } else {
            this.trigger.after(this.panel);
        }
        document.documentElement.classList.toggle("o_g2b_ss_lock", this.sheet);

        this.input.value = query;
        this.active = -1;
        this.trigger.setAttribute("aria-expanded", "true");
        this.host.classList.add("o_g2b_ss_open");
        this.render();
        if (!this.sheet) {
            this._place();
        }
        this.input.focus({ preventScroll: true });
        if (query) {
            // The typed letter, caret after it.
            this.input.setSelectionRange(query.length, query.length);
        }

        this._outside = (ev) => {
            if (!this.panel.contains(ev.target) && !this.trigger.contains(ev.target)) {
                this.close(false);
            }
        };
        this._resize = () => {
            if (PHONE.matches !== this.sheet) {
                this.close(false);
            }
        };
        document.addEventListener("pointerdown", this._outside, true);
        window.addEventListener("resize", this._resize);
    }

    close(refocus = true) {
        if (!this.isOpen) {
            return;
        }
        this.trigger.setAttribute("aria-expanded", "false");
        this.host.classList.remove("o_g2b_ss_open");
        this.panel.remove();
        document.documentElement.classList.remove("o_g2b_ss_lock");
        document.removeEventListener("pointerdown", this._outside, true);
        window.removeEventListener("resize", this._resize);
        if (refocus) {
            this.trigger.focus({ preventScroll: true });
        }
    }

    /** Under the field, as wide as it, or over it when the page has no
     * room left below. Positioned against the field's container. */
    _place() {
        const t = this.trigger;
        this.panel.style.left = `${t.offsetLeft}px`;
        this.panel.style.width = `${t.offsetWidth}px`;
        const rect = t.getBoundingClientRect();
        const room = window.innerHeight - rect.bottom;
        const needed = Math.min(this.panel.offsetHeight, 360);
        const up = room < needed + 16 && rect.top > room;
        this.panel.classList.toggle("o_g2b_ss_up", up);
        this.panel.style.top = up ? "" : `${t.offsetTop + t.offsetHeight + 4}px`;
        this.panel.style.bottom = up ? `${this.host.offsetHeight - t.offsetTop + 4}px` : "";
    }

    render() {
        const query = fold(this.input.value.trim()).folded.replace(/\s+/g, " ");
        const words = foldWords(this.input.value);
        const scored = [];
        this.items().forEach((item, index) => {
            const score = rank(item, words, query);
            if (score !== null) {
                scored.push({ item, score, index });
            }
        });
        // Always, even unfiltered: a province merged away goes last.
        scored.sort((a, b) => a.score - b.score || a.index - b.index);
        this.results = scored.map((s) => s.item);

        this.list.replaceChildren();
        this.results.forEach((item, index) => {
            const li = document.createElement("li");
            li.id = `${this.id}_opt_${index}`;
            li.setAttribute("role", "option");
            li.className = "o_g2b_ss_option";
            li.dataset.value = item.value;
            li.dataset.index = index;
            const selected = item.value === this.select.value;
            li.setAttribute("aria-selected", selected ? "true" : "false");
            const name = document.createElement("span");
            name.className = "o_g2b_ss_label";
            name.append(highlight(item, words));
            li.append(name);
            if (item.hint) {
                const hint = document.createElement("span");
                hint.className = "o_g2b_ss_hint";
                hint.textContent = item.hint;
                li.append(hint);
            }
            this.list.append(li);
        });

        this.empty.hidden = this.results.length > 0;
        if (!this.results.length) {
            this.empty.textContent = _t("No result for “%s”", this.input.value.trim());
        }
        // Start on the current choice when the list opens unfiltered.
        if (this.active < 0) {
            const current = this.results.findIndex((item) => item.value === this.select.value);
            this.active = current >= 0 ? current : 0;
        }
        this._setActive(Math.min(this.active, this.results.length - 1), true);
    }

    _setActive(index, scroll) {
        this.list.querySelector(".o_g2b_ss_active")?.classList.remove("o_g2b_ss_active");
        this.active = index;
        const li = index >= 0 ? this.list.children[index] : null;
        if (li) {
            li.classList.add("o_g2b_ss_active");
            this.input.setAttribute("aria-activedescendant", li.id);
            if (scroll) {
                li.scrollIntoView({ block: "nearest" });
            }
        } else {
            this.input.removeAttribute("aria-activedescendant");
        }
    }

    choose(value) {
        if (value !== undefined && value !== this.select.value) {
            this.select.value = value;
            this.select.classList.remove("is-invalid");
            this.select.dispatchEvent(new Event("input", { bubbles: true }));
            this.select.dispatchEvent(new Event("change", { bubbles: true }));
        }
        this.sync();
        this.close();
    }

    _onTriggerKeydown(ev) {
        if (["ArrowDown", "ArrowUp", "Enter", " "].includes(ev.key)) {
            ev.preventDefault();
            this.open();
        } else if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
            ev.preventDefault();
            this.open(ev.key);
        }
    }

    _onInputKeydown(ev) {
        const last = this.results.length - 1;
        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                this._setActive(Math.min(this.active + 1, last), true);
                break;
            case "ArrowUp":
                ev.preventDefault();
                this._setActive(Math.max(this.active - 1, 0), true);
                break;
            case "PageDown":
                ev.preventDefault();
                this._setActive(Math.min(this.active + 8, last), true);
                break;
            case "PageUp":
                ev.preventDefault();
                this._setActive(Math.max(this.active - 8, 0), true);
                break;
            case "Enter":
                // Never the form's submit.
                ev.preventDefault();
                if (this.results[this.active]) {
                    this.choose(this.results[this.active].value);
                }
                break;
            case "Escape":
                ev.preventDefault();
                ev.stopPropagation();
                this.close();
                break;
            case "Tab":
                ev.preventDefault();
                this.close();
                break;
        }
    }
}

function start() {
    if (document.body.classList.contains("editor_enable")) {
        return;
    }
    for (const select of document.querySelectorAll(SELECTOR)) {
        if (!select.dataset.g2bSsReady) {
            new SearchableSelect(select);
        }
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
} else {
    start();
}
