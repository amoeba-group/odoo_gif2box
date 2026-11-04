from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    g2b_review_ids = fields.One2many('gif2box.review', 'product_tmpl_id', string='Reviews')
    g2b_rating_avg = fields.Float(
        string='Review Rating', digits=(3, 1), compute='_compute_g2b_rating', store=True,
        help="Of the published reviews.")
    g2b_rating_count = fields.Integer(
        string='Published Reviews', compute='_compute_g2b_rating', store=True)
    g2b_review_count = fields.Integer(string='Number of Reviews', compute='_compute_g2b_review_count')

    @api.depends('g2b_review_ids.rating', 'g2b_review_ids.is_published')
    def _compute_g2b_rating(self):
        groups = self.env['gif2box.review']._read_group(
            [('product_tmpl_id', 'in', self.ids), ('is_published', '=', True)],
            ['product_tmpl_id'], ['rating:avg', '__count'])
        stats = {tmpl.id: (avg, count) for tmpl, avg, count in groups}
        for tmpl in self:
            avg, count = stats.get(tmpl.id, (0.0, 0))
            tmpl.g2b_rating_avg = round(avg or 0.0, 1)
            tmpl.g2b_rating_count = count

    def _compute_g2b_review_count(self):
        counts = dict(self.env['gif2box.review']._read_group(
            [('product_tmpl_id', 'in', self.ids)], ['product_tmpl_id'], ['__count']))
        for tmpl in self:
            tmpl.g2b_review_count = counts.get(tmpl, 0)

    def action_g2b_view_reviews(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('gif2box_review.action_reviews')
        action['domain'] = [('product_tmpl_id', '=', self.id)]
        action['context'] = {'default_product_tmpl_id': self.id, 'search_default_filter_all': 1}
        return action

    def _g2b_review_summary(self):
        """The product page's figures: average, count, the number of reviews
        per star, and the average of each kind of reviewer."""
        self.ensure_one()
        Review = self.env['gif2box.review'].sudo()
        domain = [('product_tmpl_id', '=', self.id), ('is_published', '=', True)]
        per_star = dict(Review._read_group(domain, ['rating'], ['__count']))
        per_type = {kind: (avg, count) for kind, avg, count in
                    Review._read_group(domain, ['review_type'], ['rating:avg', '__count'])}
        count = sum(per_star.values())
        with_photos = Review.search_count(domain + [('image_count', '>', 0)])
        return {
            'count_label': _("%s reviews", count) if count != 1 else _("1 review"),
            'count': count,
            'avg': round(sum(stars * n for stars, n in per_star.items()) / count, 1) if count else 0,
            'stars': [(stars, per_star.get(stars, 0), round(100 * per_star.get(stars, 0) / count) if count else 0)
                      for stars in (5, 4, 3, 2, 1)],
            'buyer': per_type.get('buyer', (0, 0)),
            'recipient': per_type.get('recipient', (0, 0)),
            'with_photos': with_photos,
            'happy_percent': round(100 * (per_star.get(5, 0) + per_star.get(4, 0)) / count) if count else 0,
        }

    def _g2b_review_domain(self, kind='all'):
        self.ensure_one()
        domain = [('product_tmpl_id', '=', self.id), ('is_published', '=', True)]
        if kind in ('buyer', 'recipient'):
            domain.append(('review_type', '=', kind))
        elif kind == 'photos':
            domain.append(('image_count', '>', 0))
        elif kind in ('1', '2', '3', '4', '5'):
            domain.append(('rating', '=', int(kind)))
        return domain

    def _g2b_reviews_page(self, kind, offset, limit):
        """A page of published reviews, and whether there are more."""
        reviews = self.env['gif2box.review'].sudo().search(
            self._g2b_review_domain(kind), offset=offset, limit=limit + 1)
        return reviews[:limit], len(reviews) > limit

    def _g2b_review_photos(self, limit=8):
        """The latest photos of the product's published reviews, for the
        strip above the list: (thumbnail, large, review)."""
        self.ensure_one()
        images = self.env['gif2box.review.image'].sudo().search(
            [('review_id.product_tmpl_id', '=', self.id), ('review_id.is_published', '=', True)],
            order='id desc', limit=limit)
        website = self.env['website'].get_current_website()
        return [(website.image_url(image, 'image_256'), website.image_url(image, 'image_1024'), image.review_id)
                for image in images]

    def _g2b_count_label(self):
        self.ensure_one()
        count = self.g2b_rating_count
        return _("%s reviews", count) if count != 1 else _("1 review")
