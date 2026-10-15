import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.image import image_data_uri, image_process

class WebsiteHeroBanner(models.Model):
    """One slide of the hero at the top of the homepage.

    The banners this replaces had their headline and their "Shop now" button
    painted into the picture: changing a word meant redrawing the image, the
    button could not be clicked, and nothing could be translated.

    A slide is built from two layers, as those banners were drawn: a
    background that runs edge to edge, and in front of it, held to the width
    of the page, the product picture on one side and the words on the other.
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
        help="Runs the full width of the screen, behind everything. Best at 1920 x 528 px. Keep it calm, a colour wash or a soft scene: the product and the text sit on top of it.")
    image_mobile = fields.Image(
        string='Mobile background', max_width=1440, max_height=1440,
        help="Optional. Shown on phones instead of the wide background, which would otherwise be cropped. Best at 1080 x 1350 px.")
    image_product = fields.Image(
        string='Product image', max_width=1600, max_height=1600,
        help="The product, on a transparent background (PNG or WebP), shown beside the text within the page width. Best at about 1200 x 1000 px. Not shown when the text is centred.")

    # Text rather than Char so the title can be broken where it should be,
    # as the artwork breaks it: Enter in the form is a new line on the page.
    title = fields.Text(
        string='Title', translate=True,
        help="Press Enter to choose where the title breaks onto a new line.")
    description = fields.Text(string='Description', translate=True)
    button_text = fields.Char(
        string='Button text', translate=True,
        default=lambda self: self.env._("Shop now"))
    button_url = fields.Char(
        string='Button link',
        help="Page the button opens, e.g. /shop/category/gift-38 or a full address. With a link but no button text, the whole banner is clickable.")

    content_position = fields.Selection(
        selection=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')],
        string='Text position', required=True, default='right',
        help="The product image takes the other side.")
    text_theme = fields.Selection(
        selection=[('dark', 'Dark text'), ('light', 'Light text')],
        string='Text colour', required=True, default='dark',
        help="Dark text for light pictures, light text for dark ones.")
    title_style = fields.Selection(
        selection=[('serif', 'Serif'), ('sans', 'Sans-serif')],
        string='Title style', required=True, default='serif',
        help="Serif for an elegant, gift-like title; sans-serif to match the rest of the site.")

    preview_html = fields.Html(
        string='Preview', compute='_compute_preview_html', sanitize=False)

    # --- Preview -----------------------------------------------------------

    @api.depends('image_desktop', 'image_product', 'title', 'description', 'button_text',
                 'content_position', 'text_theme', 'title_style')
    def _compute_preview_html(self):
        """Render the banner as the homepage will, so it can be judged here.

        Recomputed on every change in the form, before saving. The picture is
        inlined at reduced size: a new one has no URL yet.
        """
        for banner in self:
            banner.preview_html = self.env['ir.qweb']._render(
                'gif2box_hero_banner.hero_banner_preview',
                {
                    'banner': banner,
                    'image_src': banner._gif2box_preview_image_src('image_desktop', 960),
                    'product_src': banner._gif2box_preview_image_src('image_product', 480),
                },
            )

    def _gif2box_preview_image_src(self, field, width):
        """One of the banner's pictures, for the preview.

        A picture already saved is given by URL: the browser caches it, and
        the preview is re-sent on every change in the form. Only one just
        uploaded and not yet saved has no URL, and is inlined, reduced; a
        transparent product PNG inlined every time came to over 300 KB.

        Read with `bin_size` off: the web client opens forms with it on, and an
        image field then answers with its size ("49.90 Kb") instead of the
        picture.
        """
        self.ensure_one()
        raw = self.with_context(bin_size=False)[field]
        if not raw:
            return False
        origin = self._origin
        size = '%sx0' % width
        if origin.id and raw == origin.with_context(bin_size=False)[field]:
            return self.env['website'].image_url(origin, field, size=size)
        try:
            small = image_process(base64.b64decode(raw), size=(width, 0))
            return image_data_uri(base64.b64encode(small))
        except (binascii.Error, ValueError, UserError):
            return origin.id and self.env['website'].image_url(origin, field, size=size)

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

    def _gif2box_show_product(self):
        """The product image needs a side of its own, so not with centred text."""
        self.ensure_one()
        return bool(self.image_product) and self.content_position != 'center'
