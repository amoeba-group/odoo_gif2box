/**
 * Two product cards per slide on phones instead of one.
 *
 * `DEFAULT_NUMBER_OF_ELEMENTS_SM` in `@website/snippets/s_dynamic_snippet/000`
 * is 1, so below the `sm` breakpoint every carousel on the homepage showed a
 * single full-width card: one product per screenful, and four or eight swipes
 * to see a row that desktop shows at a glance. Measured on this site: the
 * combo carousel rendered `col-12`, one card per slide, under 768px and
 * `col-3`, four per slide, from 992px.
 *
 * The template derives the column class from the chunk size
 * (`col-#{12 / chunkSize}`), so raising it to 2 is all that is needed: the
 * cards come out `col-6`, which is the same width the shop grid already uses
 * on a phone.
 *
 * Only the default is changed. A snippet with "Products per slide" set
 * explicitly in the website editor keeps whatever the client chose.
 */

import { utils as uiUtils } from "@web/core/ui/ui_service";
import DynamicSnippet from "@website/snippets/s_dynamic_snippet/000";

const G2B_ELEMENTS_SM = 2;

DynamicSnippet.include({
    /**
     * @override
     */
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        if (uiUtils.isSmall() && !this.el.dataset.numberOfElementsSmallDevices) {
            const records = parseInt(this.el.dataset.numberOfRecords, 10);
            // A carousel holding a single record must stay one across, or the
            // lone card would be laid out half-width.
            options.chunkSize = Math.min(G2B_ELEMENTS_SM, records || G2B_ELEMENTS_SM);
        }
        return options;
    },
});
