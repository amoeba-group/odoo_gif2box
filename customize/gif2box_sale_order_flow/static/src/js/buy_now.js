/** @odoo-module **/

/**
 * "Buy now" for combo products.
 *
 * Every other product goes through `/shop/cart/update`, where the server
 * reads "Buy now" off the form and redirects to the checkout itself. A combo
 * is added over RPC by the combo configurator instead, which then sends the
 * shopper to the cart or leaves them on the page. Here, when the combo was
 * started from "Buy now", the route is told so (`gif2box_buy_now`, read by
 * `controllers/main.py`) and the shopper goes to the checkout.
 */

import { rpc } from "@web/core/network/rpc";
import { serializeComboItem } from "@sale/js/sale_utils";
import { WebsiteSale } from "@website_sale/js/website_sale";
// Loaded first, so this override sits on top of the one that defines it.
import "@website_sale/js/website_sale_configurators";

WebsiteSale.include({
    async addComboProductToCart(comboProductData, selectedComboItems, remainingData, options) {
        if (!this.isBuyNow) {
            return this._super(...arguments);
        }
        this._trackProducts([{
            id: this.rootProduct.product_id,
            display_name: remainingData.display_name,
            category_name: remainingData.category_name,
            currency_name: remainingData.currency_name,
            price: comboProductData.price,
            quantity: comboProductData.quantity,
        }]);
        await rpc("/website_sale/combo_configurator/update_cart", {
            combo_product_id: this.rootProduct.product_id,
            quantity: comboProductData.quantity,
            selected_combo_items: selectedComboItems.map(serializeComboItem),
            ...this._getAdditionalRpcParams(),
            gif2box_buy_now: true,
        });
        window.location = "/shop/checkout?try_skip_step=true";
    },
});
