from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Ship this module's JavaScript translations to the website.

        The frontend only fetches translations for `web` and for modules
        whose name starts with `website` (see `website/models/ir_http.py`),
        so without this the dialog title patched in
        `static/src/js/product_configurator_title.js` would stay English on
        the Vietnamese, Japanese and Korean sites.
        """
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['gif2box_theme_home']
