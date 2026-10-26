from odoo import models

# What a Vietnamese shopper may type for a country whose name in Odoo's
# Vietnamese reads otherwise ("Nam Triều tiên" for South Korea).
COUNTRY_ALIASES = {
    'KR': 'Hàn Quốc Korea',
    'KP': 'Triều Tiên',
    'US': 'Mỹ USA America',
    'GB': 'Anh UK England',
    'TW': 'Đài Loan',
    'CN': 'Tàu',
    'DE': 'Đức',
    'FR': 'Pháp',
    'AU': 'Úc',
    'RU': 'Nga',
}


class ResCountry(models.Model):
    _inherit = 'res.country'

    def _g2b_search_keywords(self):
        """Other names the country is found by in the searchable country
        field: its code, its English name, and the everyday Vietnamese one."""
        self.ensure_one()
        english = self.with_context(lang='en_US').name
        return ' '.join(filter(None, [self.code, english, COUNTRY_ALIASES.get(self.code)]))
