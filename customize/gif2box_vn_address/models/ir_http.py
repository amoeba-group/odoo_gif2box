from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Ship this module's script translations to the website.

        The frontend only fetches translations for `web` and for modules
        whose name starts with `website`; without this the searchable
        dropdowns (`static/src/js/searchable_select.js`) would say "Close"
        and "No result" in English on every site.
        """
        return super()._get_translation_frontend_modules_name() + ['gif2box_vn_address']
