import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.image import image_data_uri, image_process

class WebsiteHeroBanner(models.Model):
    """One slide of the hero at the top of the homepage.

    The banners this replaces had their headline and their "Shop now" button
    painted into the picture: changing a word meant redrawing the image, the
    button could not be clicked, and nothing could be translated. Here the
    picture is only the background, and the words and the link are fields.
    """
    _name = 'website.hero.banner'
    _description = 'Homepage Hero Banner'
    _order = 'sequence, id'

    name = fields.Char(
        string='Internal name', required=True,
        help="Only shown here, to tell the banners apart.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    website_id = fields.Many2one(
        'website', string='Website', ondelete='cascade',
        help="Leave empty to show the banner on every website.")

    # Help texts are kept to one literal each: Odoo's term extractor does not
    # join adjacent string literals, and would miss them for translation.
    image_desktop = fields.Image(
        string='Background image', required=True, max_width=2560, max_height=2560,
        help="Wide picture behind the text. Best at 1920 x 528 px, with the main subject on the opposite side from the text.")
    image_mobile = fields.Image(
        string='Mobile background', max_width=1440, max_height=1440,
        help="Optional. Shown on phones instead of the wide picture, which would otherwise be cropped. Best at 1080 x 1080 px.")

    title = fields.Char(string='Title', translate=True)
    description = fields.Text(string='Description', translate=True)
    button_text = fields.Char(
        string='Button text', translate=True,
        default=lambda self: self.env._("Shop now"))
    button_url = fields.Char(
        string='Button link',
        help="Page the button opens, e.g. /shop/category/gift-38 or a full address. With a link but no button text, the whole banner is clickable.")

    content_position = fields.Selection(
        selection=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')],
        string='Text position', required=True, default='right')
    text_theme = fields.Selection(
        selection=[('dark', 'Dark text'), ('light', 'Light text')],
        string='Text colour', required=True, default='dark',
        help="Dark text for light pictures, light text for dark ones.")

    preview_html = fields.Html(
        string='Preview', compute='_compute_preview_html', sanitize=False)

    # --- Preview -----------------------------------------------------------

    @api.depends('image_desktop', 'title', 'description', 'button_text',
                 'content_position', 'text_theme')
    def _compute_preview_html(self):
        """Render the banner as the homepage will, so it can be judged here.

        Recomputed on every change in the form, before saving. The picture is
        inlined at reduced size: a new one has no URL yet.
        """
        for banner in self:
            banner.preview_html = self.env['ir.qweb']._render(
                'gif2box_hero_banner.hero_banner_preview',
                {'banner': banner, 'image_src': banner._gif2box_preview_image_src()},
            )

    def _gif2box_preview_image_src(self):
        """The background for the preview, inlined at reduced size.

        Read with `bin_size` off: the web client opens forms with it on, and an
        image field then answers with its size ("49.90 Kb") instead of the
        picture. A saved picture that still cannot be read falls back to its
        URL; a new one has no URL yet, which is why it is inlined at all.
        """
        self.ensure_one()
        raw = self.with_context(bin_size=False).image_desktop
        if not raw:
            return False
        try:
            small = image_process(base64.b64decode(raw), size=(960, 0))
            return image_data_uri(base64.b64encode(small))
        except (binascii.Error, ValueError, UserError):
            if isinstance(self.id, int):
                return self.env['website'].image_url(self, 'image_desktop', size='960x0')
            return False

    # --- Actions -----------------------------------------------------------

    def action_view_on_website(self):
        self.ensure_one()
        website = self.website_id or self.env['website'].get_current_website()
        return {
            'type': 'ir.actions.act_url',
            'url': website.homepage_url or '/',
            'target': 'new',
        }

    # --- Rendering helpers -------------------------------------------------

    def _gif2box_link_whole_slide(self):
        """A link but no button text: the slide itself is what is clicked."""
        self.ensure_one()
        return bool(self.button_url) and not self.button_text

    def _gif2box_show_button(self):
        self.ensure_one()
        return bool(self.button_url and self.button_text)
