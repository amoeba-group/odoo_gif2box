/** @odoo-module **/
/**
 * The portal's "Your details" form with a Vietnamese address
 * (`views/portal_templates.xml`).
 *
 * Odoo's script there filters the provinces by country; this adds what
 * /shop/address does (`address_vn.js`): the ward list, reloaded when the
 * province changes, and, for Vietnam, the ward shown and "City", the second
 * address line and the postcode hidden, which the ward replaces; the other
 * way round for another country.
 *
 * Prompts are read from the page, translated with the template.
 */
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

const REPLACED_BY_WARD = ["city", "street2", "zipcode"];

publicWidget.registry.portalDetails.include({
    events: Object.assign({}, publicWidget.registry.portalDetails.prototype.events, {
        'change select[name="state_id"]': "_onG2bStateChange",
    }),

    /**
     * Odoo's pass over the form, on load and on every change of country.
     *
     * @override
     */
    _adaptAddressForm() {
        this._super(...arguments);
        const ward = this._g2bWard();
        if (!ward) {
            return;
        }
        const vietnam = this._g2bIsVietnam();
        ward.closest("#div_ward").style.display = vietnam ? "" : "none";
        for (const name of REPLACED_BY_WARD) {
            const field = this.el.querySelector(`[name="${name}"]`)?.closest('[class*="col-"]');
            if (field) {
                field.style.display = vietnam ? "none" : "";
            }
        }
        // Another country, or Vietnam picked anew: no province yet.
        if (!vietnam || !this.el.querySelector('select[name="state_id"]')?.value) {
            this._g2bResetWards("pick-state");
        }
    },

    async _onG2bStateChange() {
        if (this._g2bWard() && this._g2bIsVietnam()) {
            await this._g2bLoadWards();
        }
    },

    _g2bWard() {
        return this.el.querySelector('select[name="ward_id"]');
    },

    _g2bIsVietnam() {
        const country = this.el.querySelector('select[name="country_id"]');
        return !!country && country.value === this._g2bWard()?.dataset.g2bVnCountry;
    },

    _g2bPrompt(key) {
        return this.el.querySelector(`[data-g2b-prompt="${key}"]`)?.textContent.trim() || "";
    },

    _g2bResetWards(promptKey) {
        const select = this._g2bWard();
        select.options.length = 0;
        select.appendChild(new Option(this._g2bPrompt(promptKey), ""));
        select.disabled = promptKey === "pick-state";
    },

    async _g2bLoadWards() {
        const select = this._g2bWard();
        const stateId = parseInt(this.el.querySelector('select[name="state_id"]').value);
        if (!stateId) {
            this._g2bResetWards("pick-state");
            return;
        }
        // Two quick changes of province: only the last answer counts.
        const request = (this._g2bWardRequest = (this._g2bWardRequest || 0) + 1);
        select.disabled = true;
        const wards = await rpc("/gif2box_vn_address/wards", { state_id: stateId });
        if (request !== this._g2bWardRequest) {
            return;
        }
        this._g2bResetWards("pick-ward");
        for (const ward of wards) {
            select.appendChild(new Option(ward.name, ward.id));
        }
        select.disabled = false;
    },
});
