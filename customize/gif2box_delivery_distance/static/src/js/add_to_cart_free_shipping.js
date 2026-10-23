/** @odoo-module **/
/**
 * The free shipping bar in the "added to your cart" popup.
 *
 * Odoo hands the popup the lines just added and nothing about the cart as a
 * whole, so the bar is asked for once the popup is on screen, rendered by
 * the server from the same template as the cart page's
 * (`views/free_shipping_templates.xml`): one text, one translation. The
 * popup shows at once and the bar joins it; if the request fails, the
 * popup is simply as Odoo made it.
 */
import { markup, onMounted, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { AddToCartNotification } from "@website_sale/js/notification/add_to_cart_notification/add_to_cart_notification";

patch(AddToCartNotification.prototype, {
    setup() {
        super.setup(...arguments);
        this.g2bFreeShipping = useState({ html: "" });
        onMounted(async () => {
            try {
                const result = await rpc("/shop/gif2box/free_shipping");
                if (result && result.html) {
                    this.g2bFreeShipping.html = markup(result.html);
                }
            } catch {
                // Without the bar the popup is still complete.
            }
        });
    },
});
