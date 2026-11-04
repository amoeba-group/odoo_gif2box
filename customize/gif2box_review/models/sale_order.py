import base64
import io
import secrets

from PIL import Image

from odoo import _, api, fields, models

from .qr_svg import qr_svg

# The code in the recipient's QR link: lower case, without the characters
# people mix up (0/o, 1/l/i), as it is also printed for typing in.
CODE_ALPHABET = '23456789abcdefghjkmnpqrstuvwxyz'
CODE_LENGTH = 8

# Long names would push the card's text out of its frame.
CARD_NAME_MAX = 38


def _new_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _i in range(CODE_LENGTH))


def _short(name, limit=CARD_NAME_MAX):
    name = ' '.join((name or '').split())
    return name if len(name) <= limit else name[:limit - 1].rstrip() + '…'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    g2b_review_code = fields.Char(
        string='Recipient Review Code', copy=False, readonly=True, index=True,
        help="In the QR code of the thank-you card: opens the page where the "
             "recipient reviews this gift.")
    g2b_review_ids = fields.One2many('gif2box.review', 'order_line_id', string='Reviews')

    _sql_constraints = [
        ('g2b_review_code_uniq', 'UNIQUE(g2b_review_code)', "Two order lines cannot share a review code."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        # Set here rather than as a default: a default is applied to every
        # existing line at once, with one value.
        for vals in vals_list:
            vals.setdefault('g2b_review_code', _new_code())
        return super().create(vals_list)

    def _g2b_ensure_review_code(self):
        for line in self.filtered(lambda l: not l.g2b_review_code):
            line.g2b_review_code = _new_code()

    def _g2b_is_gift_line(self):
        """A product the customer chose: not a note, not the delivery, not
        an item inside a set (the set is reviewed as one)."""
        self.ensure_one()
        return bool(self.product_id) and not self.display_type and not self.is_delivery \
            and not self.linked_line_id and not self.is_downpayment

    def _g2b_recipient_review_url(self):
        self.ensure_one()
        return '%s/gift/%s' % (self.order_id.get_base_url(), self.g2b_review_code)

    def _g2b_review(self, review_type):
        self.ensure_one()
        return self.sudo().g2b_review_ids.filtered(lambda r: r.review_type == review_type)[:1]

    def _g2b_image_url(self, size='image_256'):
        self.ensure_one()
        website = self.order_id.website_id or self.env['website'].get_current_website()
        return website.image_url(self.product_id, size)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    g2b_review_ids = fields.One2many('gif2box.review', 'order_id', string='Reviews')
    g2b_review_count = fields.Integer(string='Number of Reviews', compute='_compute_g2b_review_count')

    @api.depends('g2b_review_ids')
    def _compute_g2b_review_count(self):
        for order in self:
            order.g2b_review_count = len(order.g2b_review_ids)

    def _g2b_gift_lines(self):
        self.ensure_one()
        return self.order_line.filtered(lambda l: l._g2b_is_gift_line())

    def _g2b_buyer_can_review(self):
        """Givers review what giving was like: once the gift has left."""
        self.ensure_one()
        return self.state == 'sale' and self.g2b_tracking_state in ('shipping', 'delivered') \
            and bool(self._g2b_gift_lines())

    def _g2b_buyer_review_url(self, line=None):
        """The giver's review page. With the order's token when it has one,
        for a guest; never creating one, as pages that only show the link
        must not write."""
        self.ensure_one()
        params = []
        if self.sudo().access_token:
            params.append('access_token=%s' % self.sudo().access_token)
        if line:
            params.append('line=%s' % line.id)
        return '/my/orders/%s/review%s' % (self.id, '?' + '&'.join(params) if params else '')

    def _g2b_review_status(self):
        """For the list of orders: 'todo' (a gift still to review), 'done'
        (all reviewed, with the average), or None (nothing to review)."""
        self.ensure_one()
        if not self._g2b_buyer_can_review():
            return None
        lines = self._g2b_gift_lines()
        reviews = self.sudo().g2b_review_ids.filtered(
            lambda r: r.review_type == 'buyer' and r.order_line_id in lines)
        if len(reviews) < len(lines):
            return {'state': 'todo', 'line': (lines - reviews.order_line_id)[:1]}
        return {'state': 'done', 'rating': round(sum(reviews.mapped('rating')) / len(reviews))}

    def _g2b_recipient_reviews(self):
        self.ensure_one()
        return self.sudo().g2b_review_ids.filtered(lambda r: r.review_type == 'recipient')

    def _g2b_giver_name(self):
        """Who the gift is from, as the card and the recipient's page name
        them: the person who ordered, not their company."""
        self.ensure_one()
        partner = self.partner_id
        return (partner.name or partner.commercial_partner_id.name or '').strip()

    # --- The thank-you card ------------------------------------------------

    def _g2b_card_lang(self):
        """The card is read by the recipient, in Vietnam: in the website's
        own language, not the language the buyer happened to shop in."""
        website = self[:1].website_id or self.env['website'].search([], limit=1)
        return website.default_lang_id.code or 'vi_VN'

    def _g2b_thank_cards(self):
        """One card per gift in the orders: who it is for, who it is from,
        and the QR code of the gift's review page."""
        cards = []
        lang = self._g2b_card_lang()
        icp = self.env['ir.config_parameter'].sudo()
        logos = {}
        for order in self.with_context(lang=lang).filtered(lambda o: o.state != 'cancel'):
            company = order.company_id
            website = order.website_id or self.env['website'].search([], limit=1)
            phone = icp.get_param('gif2box_order_tracking.support_phone') or company.phone or ''
            base_url = order.get_base_url()
            host = base_url.split('://', 1)[-1].rstrip('/')
            if host.startswith('www.'):
                host = host[4:]
            if website.id not in logos:
                logos[website.id] = self._g2b_card_logo(website.logo or company.logo)
            giver = _short(order._g2b_giver_name())
            recipient = _short(order._g2b_recipient_name())
            self_gift = order._g2b_recipient_is_buyer() or not giver
            for line in order._g2b_gift_lines():
                if not line.g2b_review_code:
                    continue
                url = line._g2b_recipient_review_url()
                cards.append({
                    'order': order,
                    'line': line,
                    'lang': lang,
                    'self_gift': self_gift,
                    'giver': giver,
                    'recipient': recipient,
                    'product': _short(line.name_short or line.product_id.name, 60),
                    'url': url,
                    'short_url': '%s/gift/%s' % (host, line.g2b_review_code),
                    'qr': qr_svg(url),
                    'phone': order._g2b_format_phone(phone),
                    'host': host,
                    'logo': logos[website.id],
                    **order._g2b_card_texts(giver, recipient, self_gift),
                })
        return cards

    @api.model
    def _g2b_card_logo(self, logo):
        """The logo as a PNG data URI, its empty margins cropped: the
        website's is a WebP, which wkhtmltopdf cannot read."""
        if not logo:
            return False
        try:
            # Odoo loads only a few of Pillow's formats, WebP not among them.
            from PIL import WebPImagePlugin  # noqa: F401
        except ImportError:
            pass
        try:
            image = Image.open(io.BytesIO(base64.b64decode(logo))).convert('RGBA')
        except Exception:
            return False
        box = image.getbbox()
        if box:
            image = image.crop(box)
        image.thumbnail((720, 320))
        out = io.BytesIO()
        image.save(out, format='PNG', optimize=True)
        return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()

    def _g2b_card_texts(self, giver, recipient, self_gift):
        """The card's sentences that hold a name. Translated here: a name
        placed inside a sentence in the template splits it into pieces a
        translator cannot reorder."""
        greeting = _("Dear %s,", recipient) if recipient else _("Hello there,")
        if self_gift:
            message = _("Thank you for choosing Gif2box to treat yourself. We packed this box "
                        "with all the care we would give our own family, and we hope it "
                        "brings you a big smile!")
            signature = _("Gif2box")
            qr_title = _("Scan to share\nhow you feel")
        else:
            message = _("%(giver)s picked this gift with all their heart and asked us to bring "
                        "it to you. Thank you, %(giver)s, for trusting Gif2box with your love, "
                        "and thank you for opening this box with a smile!", giver=giver)
            signature = _("%s & Gif2box", giver)
            # The line break is the translator's: where the title breaks well.
            qr_title = _("Scan to say thank you\nand share how you feel")
        return {'greeting': greeting, 'message': message, 'signature': signature, 'qr_title': qr_title}

    @staticmethod
    def _g2b_format_phone(phone):
        """"0987861697" as "0987 861 697"."""
        digits = ''.join(c for c in phone or '' if c.isdigit())
        if len(digits) == 10 and digits.startswith('0'):
            return '%s %s %s' % (digits[:4], digits[4:7], digits[7:])
        return phone or ''

    # --- Backend actions ---------------------------------------------------

    def action_g2b_print_thank_cards(self):
        """The cards, to look at before printing: Odoo's report view, which
        shows the report in the page with its Print button (the PDF), and
        the preview's own buttons for either size."""
        self.order_line._g2b_ensure_review_code()
        action = self.env.ref('gif2box_review.action_report_thank_card').report_action(self)
        action['report_type'] = 'qweb-html'
        return action

    def action_g2b_view_reviews(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('gif2box_review.action_reviews')
        action['domain'] = [('order_id', '=', self.id)]
        action['context'] = {'default_order_id': self.id, 'search_default_filter_all': 1}
        return action
