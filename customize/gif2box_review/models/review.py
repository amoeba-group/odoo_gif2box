import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
# Soft colours for the round initial beside a reviewer's name, picked from
# the name so that a reviewer keeps theirs.
AVATAR_COLOURS = ['#FFB39E', '#FFD27A', '#9ED9C6', '#A9C8FF', '#D8B4F8', '#F9A8C9', '#B8E08A', '#8FD3E8']

MAX_COMMENT = 2000
MAX_NOTE = 1000
MAX_NAME = 60
MAX_IMAGES = 6


class Gif2boxReview(models.Model):
    """A review of a product, by the person who gave it as a gift
    ('buyer') or by the person who received it ('recipient').

    Customers write them from the order (givers) or from the QR code of the
    thank-you card in the box (recipients); the shop can add, edit, reply
    to, hide and delete any of them."""
    _name = 'gif2box.review'
    _description = 'Product Review'
    _order = 'review_date desc, id desc'

    review_type = fields.Selection(
        [('buyer', 'Gift giver'), ('recipient', 'Gift recipient')],
        string='Written By', required=True, default='buyer', index=True,
        help="Gift giver: the customer who ordered, about giving this gift. "
             "Gift recipient: the person who received it, from the QR code "
             "of the thank-you card in the box.")
    source = fields.Selection(
        [('order', 'Order history'), ('card', 'Thank-you card'), ('shop', 'Added by the shop')],
        string='Source', default='shop', required=True, readonly=True)
    rating = fields.Integer(string='Rating', required=True, default=5, aggregator='avg')
    rating_label = fields.Char(compute='_compute_rating_label')
    comment = fields.Text(string='Review')
    tag_ids = fields.Many2many('gif2box.review.tag', string='Highlights')
    image_ids = fields.One2many('gif2box.review.image', 'review_id', string='Photos', copy=True)
    image_count = fields.Integer(string='Number of Photos', compute='_compute_image_count', store=True)

    product_tmpl_id = fields.Many2one(
        'product.template', string='Product', required=True, index=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Variant', ondelete='set null',
        domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    order_id = fields.Many2one('sale.order', string='Order', index=True, ondelete='set null')
    order_line_id = fields.Many2one('sale.order.line', string='Order Line', index=True, ondelete='set null')
    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='set null')
    website_id = fields.Many2one('website', string='Website', ondelete='cascade')

    author_name = fields.Char(string='Name', required=True)
    is_anonymous = fields.Boolean(
        string='Hide Name', help="Shown on the website as initials, like \"N***h\".")
    display_author = fields.Char(string='Shown As', compute='_compute_display_author')
    review_date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now, index=True)
    edited_date = fields.Datetime(string='Edited by the Customer On', readonly=True, copy=False)
    is_published = fields.Boolean(
        string='Published', default=True, index=True, copy=False,
        help="Shown on the product page.")
    verified = fields.Boolean(
        string='Verified', compute='_compute_verified', store=True,
        help="Written from a real order: by its buyer, or with the code of its thank-you card.")

    thanks_note = fields.Text(
        string='Note to the Gift Giver',
        help="What the recipient wrote to the person who sent the gift. Never shown on the "
             "product page: only the buyer sees it, on their order.")
    reply = fields.Text(string='Shop Reply', help="Shown under the review on the product page.")
    reply_date = fields.Datetime(string='Replied On', readonly=True, copy=False)

    _sql_constraints = [
        ('rating_range', 'CHECK(rating BETWEEN 1 AND 5)', "A rating is from 1 to 5 stars."),
        ('line_type_uniq', 'UNIQUE(order_line_id, review_type)',
         "This product of this order already has a review of this kind."),
    ]

    @api.depends('rating')
    def _compute_rating_label(self):
        for review in self:
            review.rating_label = self._g2b_rating_labels().get(review.rating, '')

    @api.depends('image_ids')
    def _compute_image_count(self):
        for review in self:
            review.image_count = len(review.image_ids)

    @api.depends('order_line_id', 'order_id')
    def _compute_verified(self):
        for review in self:
            review.verified = bool(review.order_line_id or review.order_id)

    @api.depends('author_name', 'is_anonymous')
    def _compute_display_author(self):
        for review in self:
            review.display_author = self._g2b_mask(review.author_name) if review.is_anonymous \
                else (review.author_name or '').strip()

    @api.depends('author_name', 'rating', 'product_tmpl_id')
    def _compute_display_name(self):
        for review in self:
            review.display_name = '%s · %s★ · %s' % (
                review.author_name or '', review.rating or 0, review.product_tmpl_id.name or '')

    @api.constrains('image_ids')
    def _check_image_count(self):
        for review in self:
            if len(review.image_ids) > MAX_IMAGES * 2:
                raise ValidationError(_("A review can have at most %s photos.", MAX_IMAGES * 2))

    @api.onchange('order_line_id')
    def _onchange_order_line_id(self):
        line = self.order_line_id
        if line:
            self.order_id = line.order_id
            self.product_id = line.product_id
            self.product_tmpl_id = line.product_id.product_tmpl_id
            partner = line.order_id.partner_shipping_id if self.review_type == 'recipient' \
                else line.order_id.partner_id
            self.partner_id = partner
            if not self.author_name:
                self.author_name = partner.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reply'):
                vals.setdefault('reply_date', fields.Datetime.now())
            if not vals.get('website_id') and vals.get('order_id'):
                vals['website_id'] = self.env['sale.order'].browse(vals['order_id']).website_id.id
        return super().create(vals_list)

    def write(self, vals):
        if 'reply' in vals:
            vals['reply_date'] = fields.Datetime.now() if vals['reply'] else False
        return super().write(vals)

    # --- Shown on the website ---------------------------------------------

    @staticmethod
    def _g2b_mask(name):
        """"Nguyễn Minh Anh" as "N***h"."""
        name = ''.join((name or '').split())
        if not name:
            return ''
        if len(name) <= 2:
            return name[0] + '*'
        return name[0] + '***' + name[-1]

    def _g2b_initial(self):
        self.ensure_one()
        name = (self.display_author or '?').strip()
        # The given name comes last in a Vietnamese name: "Nguyễn Minh Anh", A.
        word = name if self.is_anonymous else name.split()[-1] if name.split() else '?'
        return word[:1].upper()

    def _g2b_avatar_colour(self):
        self.ensure_one()
        digest = hashlib.md5((self.author_name or str(self.id)).encode()).digest()
        return AVATAR_COLOURS[digest[0] % len(AVATAR_COLOURS)]

    def _g2b_images_for_web(self):
        """[(thumbnail URL, large URL)], for the review card and the viewer."""
        self.ensure_one()
        website = self.env['website'].get_current_website()
        return [(website.image_url(image, 'image_256'), website.image_url(image, 'image_1024'))
                for image in self.image_ids]

    @api.model
    def _g2b_rating_labels(self):
        """What each number of stars means, as the form says it."""
        return {
            1: _("Very disappointed"),
            2: _("Not satisfied"),
            3: _("It's okay"),
            4: _("Happy"),
            5: _("Love it!"),
        }

    def action_publish(self):
        self.is_published = True

    def action_unpublish(self):
        self.is_published = False

    def action_open_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.order_id.id,
            'view_mode': 'form',
        }


class Gif2boxReviewImage(models.Model):
    _name = 'gif2box.review.image'
    _description = 'Review Photo'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    review_id = fields.Many2one('gif2box.review', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='File Name')


class Gif2boxReviewTag(models.Model):
    """A highlight a reviewer taps instead of writing it: "Beautifully
    wrapped", "Arrived on time"."""
    _name = 'gif2box.review.tag'
    _description = 'Review Highlight'
    _order = 'sequence, id'

    name = fields.Char(string='Highlight', required=True, translate=True)
    icon = fields.Char(string='Emoji', help="Shown before the highlight, like 🎁.")
    review_type = fields.Selection(
        [('buyer', 'Gift givers'), ('recipient', 'Gift recipients'), ('both', 'Both')],
        string='Offered To', required=True, default='both')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Colour')
    review_count = fields.Integer(compute='_compute_review_count')

    def _compute_review_count(self):
        counts = dict(self.env['gif2box.review']._read_group(
            [('tag_ids', 'in', self.ids)], ['tag_ids'], ['__count']))
        for tag in self:
            tag.review_count = counts.get(tag, 0)
