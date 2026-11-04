import base64
import logging
import time

from markupsafe import Markup

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.tools.image import image_process

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.review import MAX_COMMENT, MAX_IMAGES, MAX_NAME, MAX_NOTE

_logger = logging.getLogger(__name__)

# What a phone sends before `review_form.js` shrinks it, and what arrives
# untouched when the script did not run.
MAX_IMAGE_BYTES = 15 * 1024 * 1024
PAGE_SIZE = 5
PHOTO_STRIP = 8

# Wrong card codes allowed per visitor before the page asks them to wait:
# the code is all that opens a recipient's page.
MAX_FAILED_CODES = 12
CODE_WINDOW = 15 * 60


class Gif2boxReview(CustomerPortal):

    # =====================================================================
    # The recipient: the QR code of the thank-you card
    # =====================================================================

    @http.route('/gift/<string:code>', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def gift_review(self, code, **post):
        line = self._g2b_line_from_code(code)
        if not line:
            return request.render('gif2box_review.gift_not_found', {
                'g2b_wait': self._g2b_too_many_failures(),
            }, status=404)
        review = line._g2b_review('recipient')
        values = self._g2b_form_values(line, 'recipient', review, '/gift/%s' % line.g2b_review_code)
        if request.httprequest.method == 'POST':
            return self._g2b_submit(line, 'recipient', review, post, values)
        return request.render('gif2box_review.review_page', values)

    def _g2b_line_from_code(self, code):
        code = (code or '').strip().lower()
        if self._g2b_too_many_failures() or not code.isalnum() or len(code) > 16:
            return None
        line = request.env['sale.order.line'].sudo().search(
            [('g2b_review_code', '=', code)], limit=1)
        if not line or line.order_id.state == 'cancel' or not line._g2b_is_gift_line():
            self._g2b_record_failure()
            return None
        return line

    def _g2b_recent_failures(self):
        now = time.time()
        return [t for t in request.session.get('g2b_review_failures', []) if now - t < CODE_WINDOW]

    def _g2b_too_many_failures(self):
        return len(self._g2b_recent_failures()) >= MAX_FAILED_CODES

    def _g2b_record_failure(self):
        request.session['g2b_review_failures'] = self._g2b_recent_failures() + [time.time()]

    # =====================================================================
    # The giver: from the order
    # =====================================================================

    @http.route('/my/orders/<int:order_id>/review', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def order_review(self, order_id, access_token=None, line=None, **post):
        """The buyer's review of one gift of their order: signed in, or
        with the order's access token (the link in the emails and on the
        tracking page), as the order's own portal page."""
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if not order_sudo._g2b_buyer_can_review():
            return request.redirect(order_sudo._g2b_tracking_url())
        lines = order_sudo._g2b_gift_lines()
        current = lines.filtered(lambda l: str(l.id) == str(line or ''))
        if not current:
            current = (lines.filtered(lambda l: not l._g2b_review('buyer')) or lines)[:1]
        review = current._g2b_review('buyer')
        order_sudo._portal_ensure_token()
        action = order_sudo._g2b_buyer_review_url(current)
        values = self._g2b_form_values(current, 'buyer', review, action)
        values['g2b_lines'] = lines
        if request.httprequest.method == 'POST':
            return self._g2b_submit(current, 'buyer', review, post, values)
        return request.render('gif2box_review.review_page', values)

    # =====================================================================
    # Both
    # =====================================================================

    def _g2b_form_values(self, line, review_type, review, action):
        order = line.order_id
        recipient = review_type == 'recipient'
        default_name = order._g2b_recipient_name() if recipient else order._g2b_giver_name()
        tags = request.env['gif2box.review.tag'].sudo().search(
            [('review_type', 'in', (review_type, 'both'))])
        editing = bool(review) and request.params.get('edit') == '1'
        return {
            'g2b_text': self._g2b_texts(order, review_type),
            'g2b_type': review_type,
            'g2b_line': line,
            'g2b_order': order,
            'g2b_review': review,
            'g2b_editing': editing,
            'g2b_submitted': False,
            'g2b_errors': {},
            'g2b_form': {},
            'g2b_action': action,
            'g2b_tags': tags,
            'g2b_labels': request.env['gif2box.review']._g2b_rating_labels(),
            'g2b_giver': order._g2b_giver_name(),
            'g2b_recipient': order._g2b_recipient_name(),
            'g2b_self_gift': order._g2b_recipient_is_buyer(),
            'g2b_default_name': default_name,
            'g2b_product_name': line.name_short or line.product_id.name,
            'g2b_product_image': line._g2b_image_url('image_512'),
            'g2b_product_url': line.product_id.website_url if line.product_id.is_published else False,
            'g2b_kept_images': self._g2b_image_thumbs(review),
            'g2b_max_images': MAX_IMAGES,
            'g2b_max_comment': MAX_COMMENT,
            'g2b_max_note': MAX_NOTE,
            'g2b_moderated': bool(request.env['ir.config_parameter'].sudo().get_param('gif2box_review.moderate')),
        }

    @staticmethod
    def _g2b_texts(order, review_type):
        """The page's sentences that hold a name, translated whole."""
        giver = order._g2b_giver_name()
        recipient = order._g2b_recipient_name()
        self_gift = order._g2b_recipient_is_buyer() or not giver
        if review_type == 'recipient':
            texts = {
                'eyebrow': _("Hi %s!", recipient) if recipient else _("Hello!"),
                'title': _("A gift from %s, with love", giver) if not self_gift
                else _("Your Gif2box gift has arrived"),
                'lead': _("How did it feel to open it? Rate it, and send %s a thank-you note: "
                          "it only takes a minute.", giver) if not self_gift
                else _("Tell us how you like it: it only takes a minute."),
                'note_title': _("A thank-you note to %s", giver),
                'note_help': _("Only %s will see it, on their order. It is never shown on the website.", giver),
                'note_placeholder': _("Thank you so much for the gift, %s! ...", giver),
                'note_sent': _("Your note is on its way to %s.", giver),
            }
        else:
            texts = {
                'eyebrow': _("Order %s", order.name),
                'title': _("How was giving this gift?"),
                'lead': _("Your gift to %s: how did it go? Your review helps others choose a gift "
                          "for someone they love.", recipient) if not self_gift and recipient
                else _("How did it go? Your review helps others choose a gift for someone they love."),
            }
        return texts

    @staticmethod
    def _g2b_image_thumbs(review):
        """The review's photos as data URIs: the review may be waiting for
        the shop, or hidden, and its photos are then not public."""
        if not review:
            return []
        return [(image.id, 'data:image/jpeg;base64,%s' % (image.image_256 or b'').decode())
                for image in review.sudo().image_ids if image.image_256]

    def _g2b_submit(self, line, review_type, review, post, values):
        ajax = post.get('ajax') == '1'
        form = request.httprequest.form
        errors = {}

        # A field people do not see: robots fill it in.
        if post.get('g2b_company'):
            return request.make_json_response({'ok': True}) if ajax else request.redirect(request.httprequest.path)

        try:
            rating = int(post.get('rating') or 0)
        except ValueError:
            rating = 0
        if not 1 <= rating <= 5:
            errors['rating'] = _("Tap a star to give your rating.")

        comment = (post.get('comment') or '').strip()[:MAX_COMMENT]
        note = (post.get('thanks_note') or '').strip()[:MAX_NOTE] \
            if review_type == 'recipient' and not values['g2b_self_gift'] else ''
        name = ' '.join((post.get('author_name') or '').split())[:MAX_NAME] or values['g2b_default_name'] \
            or _("A Gif2box customer")
        anonymous = bool(post.get('is_anonymous'))
        tag_ids = [int(t) for t in form.getlist('tag_ids') if t.isdigit()]
        tags = values['g2b_tags'].filtered(lambda t: t.id in tag_ids)

        kept = review.image_ids.filtered(
            lambda i: str(i.id) in form.getlist('keep_image_ids')) if review else request.env['gif2box.review.image']
        files = [f for f in request.httprequest.files.getlist('images') if f and f.filename]
        photos = []
        if len(kept) + len(files) > MAX_IMAGES:
            errors['images'] = _("You can add up to %s photos.", MAX_IMAGES)
        else:
            photos, error = self._g2b_read_photos(files)
            if error:
                errors['images'] = error

        if errors:
            if ajax:
                return request.make_json_response({'ok': False, 'errors': errors})
            values.update({
                'g2b_errors': errors,
                'g2b_editing': True,
                'g2b_form': {'rating': rating, 'comment': comment, 'thanks_note': note,
                             'author_name': name, 'is_anonymous': anonymous, 'tag_ids': tags.ids},
            })
            return request.render('gif2box_review.review_page', values)

        moderated = values['g2b_moderated']
        order = line.order_id
        vals = {
            'rating': rating,
            'comment': comment,
            'thanks_note': note,
            'author_name': name,
            'is_anonymous': anonymous,
            'tag_ids': [fields.Command.set(tags.ids)],
        }
        if review:
            vals['edited_date'] = fields.Datetime.now()
            if moderated:
                vals['is_published'] = False
            review.write(vals)
            (review.image_ids - kept).unlink()
        else:
            partner = order.partner_shipping_id if review_type == 'recipient' else order.partner_id
            vals.update({
                'review_type': review_type,
                'source': 'card' if review_type == 'recipient' else 'order',
                'product_tmpl_id': line.product_id.product_tmpl_id.id,
                'product_id': line.product_id.id,
                'order_id': order.id,
                'order_line_id': line.id,
                'partner_id': partner.id,
                'website_id': order.website_id.id or request.website.id,
                'is_published': not moderated,
            })
            review = request.env['gif2box.review'].sudo().create(vals)
        if photos:
            request.env['gif2box.review.image'].sudo().create([
                {'review_id': review.id, 'name': filename, 'image_1920': data, 'sequence': 100 + index}
                for index, (filename, data) in enumerate(photos)])
        self._g2b_tell_the_shop(review, edited=bool(values['g2b_review']))

        if ajax:
            return request.make_json_response({'ok': True})
        values.update({'g2b_review': review, 'g2b_submitted': True, 'g2b_editing': False})
        return request.render('gif2box_review.review_page', values)

    @staticmethod
    def _g2b_read_photos(files):
        """[(file name, base64 JPEG)], re-encoded: resized to 1920 px at most,
        turned upright, and stripped of what a phone puts in a photo's
        metadata (the place it was taken, among others)."""
        try:
            # Odoo loads only a few of Pillow's formats; phones send WebP too.
            from PIL import WebPImagePlugin  # noqa: F401
        except ImportError:
            pass
        photos = []
        for upload in files[:MAX_IMAGES]:
            data = upload.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                return [], _("This photo is too large: %s. Please choose one under 15 MB.", upload.filename)
            try:
                jpeg = image_process(data, size=(1920, 1920), verify_resolution=True,
                                     quality=86, output_format='JPEG')
            except (UserError, ValueError, OSError):
                return [], _("This file could not be read as a photo: %s. Please choose a JPEG or PNG photo.",
                             upload.filename)
            photos.append(((upload.filename or 'photo.jpg')[:120], base64.b64encode(jpeg)))
        return photos, None

    @staticmethod
    def _g2b_tell_the_shop(review, edited):
        """A note in the order's chatter, so that the shop sees the review
        where it works, and can answer it."""
        order = review.order_id
        if not order:
            return
        kind = _("the gift giver") if review.review_type == 'buyer' else _("the recipient")
        stars = '★' * review.rating + '☆' * (5 - review.rating)
        title = _("Review edited by %(who)s: %(stars)s", who=kind, stars=stars) if edited \
            else _("New review by %(who)s: %(stars)s", who=kind, stars=stars)
        body = Markup('<p><strong>%s</strong></p>') % title
        if review.comment:
            body += Markup('<p>%s</p>') % review.comment
        if review.thanks_note:
            body += Markup('<p><em>%s</em> %s</p>') % (_("Note to the giver:"), review.thanks_note)
        if review.image_count:
            body += Markup('<p>%s</p>') % _("%s photo(s).", review.image_count)
        try:
            order.sudo().message_post(body=body, message_type='comment', subtype_xmlid='mail.mt_note')
        except Exception:
            _logger.exception("Could not note the review on %s", order.name)

    # =====================================================================
    # The product page: more reviews, filtered
    # =====================================================================

    @http.route('/shop/reviews/<int:product_tmpl_id>', type='http', auth='public', website=True,
                sitemap=False, methods=['GET'], readonly=True)
    def product_reviews(self, product_tmpl_id, kind='all', offset=0, **kw):
        product = request.env['product.template'].sudo().browse(product_tmpl_id).exists()
        if not product or not product.is_published:
            return request.not_found()
        try:
            offset = max(int(offset), 0)
        except ValueError:
            offset = 0
        reviews, more = product._g2b_reviews_page(kind, offset, PAGE_SIZE)
        return request.render('gif2box_review.product_review_items', {
            'g2b_reviews': reviews,
            'g2b_more': more,
            'g2b_next': offset + len(reviews),
            'g2b_kind': kind,
            'g2b_empty': not reviews and not offset,
        }, headers={'Cache-Control': 'no-store'})
