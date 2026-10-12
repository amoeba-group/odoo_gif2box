from odoo import _
from odoo.http import request, route

from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleVnAddress(WebsiteSale):
    """The address form, in the order a Vietnamese address is written.

    Country, then province or city, then ward or commune, then the street
    line. Since 1 July 2025 there is no district in between, and the old
    free-text "City" field is gone for Vietnam: its role is taken by the
    ward, whose name is written into `city` on save so that everything that
    prints an address keeps working.

    Other countries keep Odoo's own form and rules.
    """

    # --- What the form is rendered with ----------------------------------

    def _prepare_address_form_values(self, order_sudo, partner_sudo, *args, **kwargs):
        values = super()._prepare_address_form_values(order_sudo, partner_sudo, *args, **kwargs)
        vietnam = request.env.ref('base.vn').sudo()

        # Vietnam, always: the shop delivers nowhere else. Odoo would guess
        # from the visitor's IP, or keep the country an older address was
        # saved with; either way the form would be for the wrong country.
        values['country'] = vietnam
        values['countries'] = vietnam
        values['country_states'] = request.env['res.country.state']._vn_current_provinces()

        values['vn_wards'] = request.env['res.country.ward'].sudo()
        state = partner_sudo.state_id
        if state in values['country_states']:
            values['vn_wards'] = state.ward_ids._sorted_for_display()
        return values

    @route()
    def shop_country_info(self, country, address_type, **kw):
        info = super().shop_country_info(country, address_type, **kw)
        if country.code == 'VN':
            # The same 34 the form was rendered with, in the same order.
            info['states'] = [
                (state.id, state.name, state.code)
                for state in request.env['res.country.state']._vn_current_provinces()
            ]
        return info

    @route('/gif2box_vn_address/wards', type='json', auth='public', website=True, readonly=True)
    def gif2box_vn_wards(self, state_id):
        """The wards of one province, for the dropdown under it."""
        state = request.env['res.country.state'].sudo().browse(int(state_id)).exists()
        if not state or not state.vn_gso_code:
            return []
        return [{'id': ward.id, 'name': ward.name} for ward in state.ward_ids._sorted_for_display()]

    # --- What the form must contain ---------------------------------------

    # Applied to the two final lists rather than to `_get_mandatory_address_fields`
    # underneath them: the billing list adds the portal's own required fields
    # on top of that one, `city` among them, so a change made lower down is
    # undone before it reaches the form.

    def _get_mandatory_billing_address_fields(self, country_sudo):
        return self._vn_mandatory_fields(
            super()._get_mandatory_billing_address_fields(country_sudo), country_sudo)

    def _get_mandatory_delivery_address_fields(self, country_sudo):
        return self._vn_mandatory_fields(
            super()._get_mandatory_delivery_address_fields(country_sudo), country_sudo)

    def _vn_mandatory_fields(self, field_names, country_sudo):
        if country_sudo.code == 'VN':
            # `city` is written from the ward on save; asked for on the form
            # as well, it would be a second, hidden copy of the same answer.
            field_names = (set(field_names) - {'city', 'zip'}) | {'state_id', 'ward_id'}
        return field_names

    def _parse_form_data(self, form_data):
        address_values, extra_form_data = super()._parse_form_data(form_data)
        # The form offers Vietnam and nothing else; this is what makes that
        # true of whatever is actually posted.
        address_values['country_id'] = request.env.ref('base.vn').id
        return address_values, extra_form_data

    def _validate_address_values(self, address_values, partner_sudo, address_type, *args, **kwargs):
        invalid_fields, missing_fields, error_messages = super()._validate_address_values(
            address_values, partner_sudo, address_type, *args, **kwargs
        )
        country = request.env['res.country'].sudo().browse(address_values.get('country_id'))
        if country.code != 'VN':
            return invalid_fields, missing_fields, error_messages

        state = request.env['res.country.state'].sudo().browse(address_values.get('state_id'))
        ward = request.env['res.country.ward'].sudo().browse(address_values.get('ward_id'))

        # Only reachable with a stale form or a hand-made request: the form
        # offers nothing else.
        if state and not state.vn_gso_code:
            invalid_fields.add('state_id')
            # One literal: Odoo's term extractor does not join adjacent ones.
            error_messages.append(_("This province no longer exists after the 2025 merger. Please choose its current province or city."))
        elif ward and ward.state_id != state:
            invalid_fields.add('ward_id')
            error_messages.append(_(
                "The selected ward or commune is not in the selected province or city."
            ))
        return invalid_fields, missing_fields, error_messages
