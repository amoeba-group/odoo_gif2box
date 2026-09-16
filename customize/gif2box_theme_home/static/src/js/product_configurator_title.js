/**
 * Retitles the product configurator dialog.
 *
 * Odoo calls it "Configure your product", which reads like back-office
 * language. On a shop the shopper is picking a size or a colour, so the
 * heading says that instead.
 *
 * The string goes through `_t`, and the module ships translations, so the
 * wording follows the visitor's language rather than being pinned to one.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    ProductConfiguratorDialog,
} from "@sale/js/product_configurator_dialog/product_configurator_dialog";

patch(ProductConfiguratorDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.title = _t("Choose your options");
    },
});
