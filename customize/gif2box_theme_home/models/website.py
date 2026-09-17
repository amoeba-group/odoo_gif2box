import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# --- The menu this module owns -------------------------------------------
#
# Menus and pages are normally website content: Odoo keeps them in the
# database and the client edits them from Site -> Menu Editor, which means
# they do not travel with the code. The structure below is declared here
# instead and applied on every update of this module, so a deploy lands the
# same bar on every database.
#
# The trade is the usual one for taking content into code: edits made to
# *these* entries in the Menu Editor are put back the next time the module is
# updated. Anything else the client adds to the bar is left alone.

ABOUT_URL = '/ve-chung-toi'

ABOUT_NAMES = {
    'en_US': 'About Us',
    'vi_VN': 'Về Chúng Tôi',
    'ja_JP': '会社概要',
    'ko_KR': '회사 소개',
}

POLICY_NAMES = {
    'en_US': 'Policies',
    'vi_VN': 'Chính sách',
    'ja_JP': 'ポリシー',
    'ko_KR': '정책',
}

# The pages that belong under "Policies", in the order they should appear.
POLICY_URLS = [
    '/chinh-sach-bao-mat-thong-tin',
    '/dieu-khoan-va-dieu-kien',
    '/chinh-sach-doi-tra-va-hoan-tien',
    '/chinh-sach-thanh-toan',
    '/chinh-sach-van-chuyen-va-giao-nhan',
    '/chinh-sach-ve-gia',
    '/cac-dieu-kien-va-han-che-trong-viec-cung-cap-hang-hoa-dich-vu-tren-nen-tang',
    '/phuong-thuc-tiep-nhan-va-giai-quyet-phan-anh-yeu-cau-khieu-nai',
]

# Top level order; the policy parent is appended after these.
TOP_ORDER = ['/', ABOUT_URL, '/shop/category/34', '/shop/category/gift-38']


class Website(models.Model):
    _inherit = 'website'

    def _gif2box_write_translations(self, record, field, names):
        """Write one field in every language the database has installed."""
        installed = self.env['res.lang'].search([]).mapped('code')
        for code, value in names.items():
            if code in installed:
                record.with_context(lang=code).write({field: value})

    @api.model
    def _gif2box_setup_menu(self):
        """Lay out the top menu: Home, About, Life, Gift, Policies.

        `@api.model` because `<function>` in a data file passes no ids:
        without it `call_kw` treats this as a multi-record method and fails
        reading the record ids out of an empty argument list.

        Called from `data/menu_data.xml` on every install and update, and
        safe to run any number of times: everything is matched on page URLs,
        and a second pass finds its own work already done.

        Runs for every website in the database, so a second site added later
        is covered without touching this file.
        """
        for website in self.env['website'].search([]):
            self._gif2box_setup_menu_one(website)

    def _gif2box_setup_menu_one(self, website):
        env_w = self.env(context=dict(self.env.context, website_id=website.id))
        Menu = env_w['website.menu']
        root = Menu.search(
            [('website_id', '=', website.id), ('parent_id', '=', False)], limit=1)
        if not root:
            _logger.warning('gif2box menu: website %s has no root menu, skipped', website.id)
            return

        # --- About Us page ---------------------------------------------
        page = env_w['website.page'].search(
            [('url', '=', ABOUT_URL), ('website_id', 'in', (website.id, False))], limit=1)
        if not page:
            result = website.with_context(website_id=website.id).new_page(
                name=ABOUT_NAMES['en_US'],
                add_menu=False,
                page_values={'url': ABOUT_URL, 'is_published': True},
            )
            page = env_w['website.page'].browse(result['page_id'])
            page.write({'url': ABOUT_URL, 'is_published': True})
            _logger.info('gif2box menu: created page %s', ABOUT_URL)

        about = Menu.search(
            [('website_id', '=', website.id), ('url', '=', ABOUT_URL)], limit=1)
        if not about:
            about = Menu.create({
                'name': ABOUT_NAMES['en_US'],
                'url': ABOUT_URL,
                'page_id': page.id,
                'parent_id': root.id,
                'website_id': website.id,
            })
        self._gif2box_write_translations(about, 'name', ABOUT_NAMES)

        # --- Policies parent --------------------------------------------
        parent = Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', root.id),
            ('name', 'in', list(POLICY_NAMES.values())),
            # It holds the submenu and links nowhere of its own; Odoo renders
            # a menu without a real URL as a dropdown toggle.
            ('url', 'in', (False, '#')),
        ], limit=1)
        if not parent:
            parent = Menu.create({
                'name': POLICY_NAMES['en_US'],
                'url': '#',
                'parent_id': root.id,
                'website_id': website.id,
            })
        self._gif2box_write_translations(parent, 'name', POLICY_NAMES)

        # --- Move the policy entries under it ----------------------------
        found = 0
        for index, url in enumerate(POLICY_URLS):
            menu = Menu.search(
                [('website_id', '=', website.id), ('url', '=', url)], limit=1)
            if not menu:
                continue
            menu.write({'parent_id': parent.id, 'sequence': index})
            found += 1
        if not found:
            _logger.warning(
                'gif2box menu: none of the policy URLs matched a menu on website %s. '
                'Are the page URLs on this database the ones listed in POLICY_URLS?',
                website.id)

        # --- Order the top level -----------------------------------------
        for index, url in enumerate(TOP_ORDER):
            menu = Menu.search([
                ('website_id', '=', website.id),
                ('parent_id', '=', root.id),
                ('url', '=', url),
            ], limit=1)
            if menu:
                menu.sequence = index
        parent.sequence = len(TOP_ORDER)

        _logger.info(
            'gif2box menu: website %s laid out, %s policy entries in the submenu',
            website.id, found)
