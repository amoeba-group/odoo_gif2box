/**
 * The Vietnamese address flow on /shop/address.
 *
 * Odoo's address widget already reacts to a change of country: it reloads
 * the province list, shows or hides street, postcode and city, and marks
 * whichever fields the server says are required (for Vietnam that now
 * includes the ward, so the asterisk and the browser's own check come for
 * free). This adds the two things it does not know about:
 *
 *   - the ward dropdown, reloaded whenever the province changes;
 *   - for Vietnam, hiding the fields the ward replaces: city, postcode and
 *     "Apartment, suite". Done after Odoo's own pass, which would otherwise
 *     show the city again.
 *
 * Prompts are read from the page rather than passed through `_t`, so they are
 * translated with the template and this file needs no translation bundle.
 */
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

const VIETNAM = "VN";
const REPLACED_BY_WARD = ["city", "zip", "street2"];

publicWidget.registry.websiteSaleAddress.include({
    /**
     * @override
     */
    async _changeCountry(init = false) {
        await this._super(...arguments);
        if (!this.addressForm.ward_id) {
            return;
        }
        const vietnam = this._g2bIsVietnam();

        for (const name of REPLACED_BY_WARD) {
            if (!this.addressForm[name]) {
                continue;
            }
            if (vietnam) {
                this._hideInput(name);
            } else if (name === "street2") {
                // Odoo never hides it, so it never shows it again either.
                this._showInput(name);
            }
        }

        if (vietnam) {
            this._showInput("ward_id");
            // On the first pass the list was rendered by the server for the
            // saved province; a real change of country starts it over.
            if (!init) {
                this._g2bResetWards("pick-state");
            }
        } else {
            this._hideInput("ward_id");
            this._g2bResetWards("pick-state");
        }
    },

    /**
     * @override
     */
    async _onChangeState(ev) {
        await this._super(...arguments);
        if (this.addressForm.ward_id && this._g2bIsVietnam()) {
            await this._g2bLoadWards();
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _g2bIsVietnam() {
        const option = this.addressForm.country_id?.selectedOptions[0];
        return option?.getAttribute("code") === VIETNAM;
    },

    _g2bPrompt(key) {
        return this.el.querySelector(`[data-g2b-prompt="${key}"]`)?.textContent.trim() || "";
    },

    _g2bResetWards(promptKey) {
        const select = this.addressForm.ward_id;
        select.options.length = 0;
        select.appendChild(new Option(this._g2bPrompt(promptKey), ""));
        select.disabled = promptKey === "pick-state";
    },

    async _g2bLoadWards() {
        const select = this.addressForm.ward_id;
        const stateId = parseInt(this.addressForm.state_id.value);
        if (!stateId) {
            this._g2bResetWards("pick-state");
            return;
        }

        // A shopper changing province twice in quick succession must not end
        // up with the first province's wards because that answer came back
        // last.
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
