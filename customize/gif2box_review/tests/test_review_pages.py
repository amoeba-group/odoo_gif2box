"""The review pages, end to end, through HTTP.

Everything a test writes is rolled back with its transaction: no order is
created (orders consume sequence numbers, which a rollback does not give
back); the tests use the database's own confirmed orders and skip when it
has none that fit.
"""
import base64
import io
import json
import re

from PIL import Image

from odoo.tests import HttpCase, tagged


def _jpeg(width=2400, height=1800):
    out = io.BytesIO()
    Image.new('RGB', (width, height), (253, 115, 82)).save(out, format='JPEG')
    return out.getvalue()


@tagged('post_install', '-at_install')
class TestReviewPages(HttpCase):

    def setUp(self):
        super().setUp()
        Line = self.env['sale.order.line']
        self.line = Line.search([
            ('order_id.state', '=', 'sale'), ('g2b_review_code', '!=', False),
            ('linked_line_id', '=', False), ('is_delivery', '=', False), ('display_type', '=', False),
            ('product_id.is_published', '=', True)], limit=1)
        if not self.line:
            self.skipTest("No confirmed order to review in this database.")
        self.order = self.line.order_id
        self.env['ir.config_parameter'].sudo().set_param('gif2box_review.moderate', False)

    def _csrf(self, html):
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def _post(self, url, data, files=None):
        page = self.url_open(url)
        self.assertEqual(page.status_code, 200, page.text[:300])
        data = dict(data, csrf_token=self._csrf(page.text), ajax='1')
        return self.url_open(url, data=data, files=files or {})

    def test_recipient_review_with_photo_and_note(self):
        url = '/gift/%s' % self.line.g2b_review_code
        page = self.url_open(url)
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_g2b_rvf_form', page.text)
        tag = self.env['gif2box.review.tag'].search([('review_type', 'in', ('recipient', 'both'))], limit=1)
        response = self._post(url, {
            'rating': '5', 'comment': 'So lovely!', 'thanks_note': 'Thank you so much!',
            'author_name': 'Test Recipient', 'tag_ids': str(tag.id),
        }, files={'images': ('box.jpg', _jpeg(), 'image/jpeg')})
        self.assertEqual(response.json(), {'ok': True})

        review = self.env['gif2box.review'].search([('order_line_id', '=', self.line.id), ('review_type', '=', 'recipient')])
        self.assertEqual(len(review), 1)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.source, 'card')
        self.assertTrue(review.is_published)
        self.assertEqual(review.thanks_note, 'Thank you so much!')
        self.assertEqual(review.tag_ids, tag)
        self.assertEqual(review.image_count, 1)
        # Resized to 1920 px, re-encoded (no camera metadata kept).
        image = Image.open(io.BytesIO(base64.b64decode(review.image_ids.image_1920)))
        self.assertLessEqual(max(image.size), 1920)
        self.assertEqual(image.format, 'JPEG')
        # The shop is told on the order.
        self.assertIn('So lovely!', self.order.message_ids[:1].body)

        # Shown on the product page, with its photo and the aggregate rating.
        product = self.line.product_id.product_tmpl_id
        product_page = self.url_open(product.website_url)
        self.assertIn('So lovely!', product_page.text)
        self.assertIn('itemprop="aggregateRating"', product_page.text)
        self.assertIn('o_g2b_rv_inline', product_page.text)
        # Never the private note.
        self.assertNotIn('Thank you so much!', product_page.text)
        photo = re.search(r'data-g2b-full="([^"]+)"', product_page.text).group(1)
        self.assertEqual(self.url_open(photo).status_code, 200)

        # Filtered fragments.
        self.assertIn('So lovely!', self.url_open('/shop/reviews/%s?kind=photos' % product.id).text)
        self.assertNotIn('So lovely!', self.url_open('/shop/reviews/%s?kind=buyer' % product.id).text)

        # Coming back: the review, and a way to edit it, which keeps the photo.
        again = self.url_open(url)
        self.assertIn('o_g2b_rvf_done', again.text)
        edit = self.url_open(url + '?edit=1')
        self.assertIn('keep_image_ids', edit.text)
        response = self.url_open(url, data={
            'csrf_token': self._csrf(edit.text), 'ajax': '1', 'rating': '4', 'comment': 'Still lovely',
            'author_name': 'Test Recipient', 'keep_image_ids': str(review.image_ids.id),
            'thanks_note': review.thanks_note,
        })
        self.assertEqual(response.json(), {'ok': True})
        review.invalidate_recordset()
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.image_count, 1)
        self.assertTrue(review.edited_date)

        # The buyer reads the note on their order.
        token = self.order._portal_ensure_token()
        track = self.url_open('/order/track/%s?access_token=%s' % (self.order.id, token))
        self.assertIn('o_g2b_rvp_letter', track.text)

    def test_moderated_review_waits(self):
        self.env['ir.config_parameter'].sudo().set_param('gif2box_review.moderate', True)
        url = '/gift/%s' % self.line.g2b_review_code
        self.assertEqual(self._post(url, {'rating': '3', 'author_name': 'X'}).json(), {'ok': True})
        review = self.env['gif2box.review'].search([('order_line_id', '=', self.line.id)])
        self.assertFalse(review.is_published)
        product_page = self.url_open(self.line.product_id.product_tmpl_id.website_url)
        self.assertNotIn('itemprop="aggregateRating"', product_page.text)

    def test_refusals(self):
        url = '/gift/%s' % self.line.g2b_review_code
        # No rating.
        response = self._post(url, {'comment': 'no stars'})
        self.assertIn('rating', response.json()['errors'])
        # Not a photo.
        response = self._post(url, {'rating': '5'}, files={'images': ('evil.jpg', b'not an image', 'image/jpeg')})
        self.assertIn('images', response.json()['errors'])
        # Too many photos.
        files = [('images', ('p%s.jpg' % i, _jpeg(40, 40), 'image/jpeg')) for i in range(7)]
        response = self._post(url, {'rating': '5'}, files=files)
        self.assertIn('images', response.json()['errors'])
        self.assertFalse(self.env['gif2box.review'].search([('order_line_id', '=', self.line.id)]))
        # Robots: the hidden field filled in, nothing saved.
        self._post(url, {'rating': '5', 'g2b_company': 'spam'})
        self.assertFalse(self.env['gif2box.review'].search([('order_line_id', '=', self.line.id)]))
        # A code that does not exist.
        self.assertEqual(self.url_open('/gift/zzzzzzzz').status_code, 404)

    def test_buyer_review(self):
        order = self.env['sale.order'].search([
            ('state', '=', 'sale'), ('g2b_tracking_state', 'in', ('shipping', 'delivered'))], limit=1)
        if not order:
            self.skipTest("No order that has left in this database.")
        line = order._g2b_gift_lines()[:1]
        token = order._portal_ensure_token()
        url = '/my/orders/%s/review?access_token=%s&line=%s' % (order.id, token, line.id)
        response = self._post(url, {'rating': '5', 'comment': 'Easy and quick', 'author_name': 'Test Giver',
                                    'is_anonymous': '1', 'thanks_note': 'ignored for givers'})
        self.assertEqual(response.json(), {'ok': True})
        review = self.env['gif2box.review'].search([('order_line_id', '=', line.id), ('review_type', '=', 'buyer')])
        self.assertEqual(review.source, 'order')
        self.assertEqual(review.display_author, 'T***r')
        self.assertFalse(review.thanks_note)
        self.assertEqual(order._g2b_review_status()['state'], 'done' if len(order._g2b_gift_lines()) == 1 else 'todo')
        # Without the token, a visitor is sent away.
        self.assertNotIn('o_g2b_rvf_form', self.url_open('/my/orders/%s/review' % order.id).text)

    def test_thank_card_pdf(self):
        report = self.env['ir.actions.report']
        pdf, kind = report.with_context(force_report_rendering=True)._render_qweb_pdf(
            'gif2box_review.action_report_thank_card', self.order.ids)
        self.assertEqual(kind, 'pdf')
        self.assertTrue(pdf.startswith(b'%PDF'))
        html = report._render_qweb_html('gif2box_review.action_report_thank_card', self.order.ids)[0]
        self.assertIn(self.line.g2b_review_code, html.decode() if isinstance(html, bytes) else html)
