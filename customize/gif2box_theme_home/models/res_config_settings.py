import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def _gif2box_enable_price_comparison(self):
        """Switch on Odoo's "Comparison Price" setting.

        It is what reveals `product.template.compare_list_price` -- the
        "Compare to Price" field next to the sales price on the product form --
        and what makes `_get_combination_info` return it to the templates.
        Without it the field is hidden and the strikethrough never renders.

        This is a setting, so the natural home would be a `<record>` on
        `base.group_user`'s `implied_ids`. That does not work: the group's
        `ir_model_data` row is flagged `noupdate`, which is Odoo protecting
        user-group configuration from module data, so the record would be
        skipped in silence. Calling `write` from a `<function>` goes through
        the ORM, which also pushes the group down to everyone who already has
        the parent group.

        Portal and public are included on purpose. Ticking the setting in the
        UI only grants it to internal users, and both the strikethrough and the
        price that feeds it are gated on `env.user.has_group(...)` -- so with
        internal alone the merchant sees the comparison price while logged in
        and no shopper ever does, which is the opposite of what the feature is
        for. Nothing is exposed that was not meant to be: the field holds a
        price the merchant typed in to be displayed.

        Called from `data/settings_data.xml` on install and update, and safe to
        repeat: adding a group already present is a no-op.
        """
        comparison = self.env.ref(
            'website_sale.group_product_price_comparison', raise_if_not_found=False)
        if not comparison:
            _logger.warning('gif2box: comparison price group not found, skipped')
            return

        granted = []
        for xmlid in ('base.group_user', 'base.group_portal', 'base.group_public'):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group and comparison not in group.implied_ids:
                group.sudo().write({'implied_ids': [(4, comparison.id)]})
                granted.append(xmlid)

        if granted:
            _logger.info('gif2box: comparison price enabled for %s', ', '.join(granted))
