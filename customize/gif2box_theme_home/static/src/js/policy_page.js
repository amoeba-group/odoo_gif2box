/**
 * Collapses the blank paragraphs in the policy pages.
 *
 * The copy was pasted in section by section and carries 20 empty paragraphs
 * out of 57 on one page alone: 13 of them `<p><br></p>`, the rest holding
 * nothing but a non-breaking space. Each one is a full blank line, so the
 * text reads as if the sections had drifted apart.
 *
 * `<p><br></p>` is reachable from CSS and is handled in `policy_page.scss`;
 * a paragraph holding `&nbsp;` is not, because as far as a selector is
 * concerned it has content. Hence this.
 *
 * Nothing is deleted -- the paragraphs are only hidden, so the client's page
 * content is untouched and the change is undone by removing this file. The
 * website editor renders the site in an iframe, and skipping that case leaves
 * the blank paragraphs visible and selectable while editing.
 */

(function () {
    "use strict";

    function setup() {
        if (window.self !== window.top) {
            // In the editor's iframe: leave the content exactly as it is.
            return;
        }
        const page = document.querySelector(".s_table_of_content");
        if (!page) {
            return;
        }
        // Headings too: the copy carries empty `<h2>` elements, and each one
        // is both a gap in the text and a blank row in the sidebar, because
        // the table of contents lists every heading it finds.
        const blankable = page.querySelectorAll(
            ".s_table_of_content_main p,"
            + " .s_table_of_content_main h2,"
            + " .s_table_of_content_main h3,"
            + " .s_table_of_content_main h4,"
            + " .table_of_content_link"
        );
        for (const el of blankable) {
            // An element carrying an image or an embed is not blank whatever
            // its text says.
            if (el.querySelector("img, iframe, svg, video")) {
                continue;
            }
            if (!el.textContent.replace(/ /g, " ").trim()) {
                el.classList.add("o_g2b_blank_p");
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
