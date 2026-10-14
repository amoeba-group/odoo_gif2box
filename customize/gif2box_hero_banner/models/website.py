from odoo import models


class Website(models.Model):
    _inherit = 'website'

    def _gif2box_hero_banners(self):
        """The active banners of this website, in the order they slide."""
        self.ensure_one()
        return self.env['website.hero.banner'].sudo().search([
            ('website_id', 'in', (False, self.id)),
        ])

    def _gif2box_is_homepage(self, main_object):
        """Whether the page being rendered is this website's homepage."""
        self.ensure_one()
        return (
            bool(main_object)
            and main_object._name == 'website.page'
            and main_object.url == (self.homepage_url or '/')
        )
