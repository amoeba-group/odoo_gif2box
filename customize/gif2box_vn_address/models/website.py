from odoo import models


class Website(models.Model):
    _inherit = 'website'

    def _display_partner_b2b_fields(self):
        """Keep "Company name" and the VAT number off the address form.

        Odoo shows them when the "B2B fields" option of the address page is
        on, and localisations may force them; none does for Vietnam. Answered
        here rather than by switching the option off, so it holds whatever is
        later ticked in the website editor.
        """
        return False
