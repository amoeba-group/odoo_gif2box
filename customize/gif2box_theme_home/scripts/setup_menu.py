"""Restructure the top menu: Home, About, Life, Gift, Policies (with submenu).

Menus and pages are website content, not module data: Odoo owns them in the
database and the client edits them from Site -> Menu Editor. They do not
travel with the code, so this script exists to make the same change on any
database rather than being repeated by hand across eight menu entries.

Run it once per database:

    echo "exec(open(r'<abs path>/setup_menu.py', encoding='utf-8').read())" \
        | odoo-bin shell -c odoo.conf -d <database> --no-http

Piping the file straight in (`shell ... < setup_menu.py`) fails on Windows:
the shell reads stdin in the console codepage and chokes on the Vietnamese,
Japanese and Korean names. The `exec(open(..., encoding='utf-8'))` line is
pure ASCII, so it survives the pipe and reads the file itself.

It is safe to run twice: everything is keyed on the page URLs, and a second
run finds the menus already in place and leaves them alone.

The set of menu ids per website is `ormcache`d, so a server that is already
running will keep serving the old bar until it is told otherwise. Writing the
records marks the cache dirty in *this* process, but only `signal_changes()`
writes the sequence the other processes poll, and nothing in `odoo-bin shell`
calls it -- so the script calls it itself at the end. If the old menu somehow
survives that, restart Odoo.
"""

# Leave as None to use the only website there is; the script stops rather than
# guessing if the database has several.
WEBSITE_ID = None

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

# Top level order. The policy parent is appended last.
TOP_ORDER = ['/', ABOUT_URL, '/shop/category/34', '/shop/category/gift-38']


def _write_translations(record, field, names):
    """Write one field in every language the site has active."""
    active = env['res.lang'].search([]).mapped('code')
    for code, value in names.items():
        if code in active:
            record.with_context(lang=code).write({field: value})


def _print_tree(Menu, root, title):
    print('\n%s' % title)
    for menu in Menu.search([('parent_id', '=', root.id)], order='sequence, id'):
        print('  %-26s %s' % (menu.name, menu.url))
        for child in Menu.search([('parent_id', '=', menu.id)], order='sequence, id'):
            print('      %-22s %s' % (child.name, child.url))


def run():
    website_id = WEBSITE_ID
    if website_id is None:
        websites = env['website'].search([])
        if len(websites) != 1:
            raise Exception(
                'Found %s websites (%s). Set WEBSITE_ID at the top of this '
                'script to the one you mean.'
                % (len(websites), ', '.join('%s=%s' % (w.id, w.name) for w in websites)))
        website_id = websites.id

    website = env['website'].browse(website_id)
    print('Website: %s (id %s)' % (website.name, website_id))

    env_w = env(context=dict(env.context, website_id=website_id))
    Menu = env_w['website.menu']
    root = Menu.search([('website_id', '=', website_id), ('parent_id', '=', False)], limit=1)
    if not root:
        raise Exception('No root menu found for website %s' % website_id)

    _print_tree(Menu, root, 'Top menu before:')

    # --- About Us page ------------------------------------------------
    page = env_w['website.page'].search(
        [('url', '=', ABOUT_URL), ('website_id', 'in', (website_id, False))], limit=1)
    if page:
        print('\nAbout page already exists:', page.url)
    else:
        result = website.with_context(website_id=website_id).new_page(
            name=ABOUT_NAMES['en_US'],
            add_menu=False,
            page_values={'url': ABOUT_URL, 'is_published': True},
        )
        page = env_w['website.page'].browse(result['page_id'])
        page.write({'url': ABOUT_URL, 'is_published': True})
        print('\nCreated About page:', page.url)

    about_menu = Menu.search([('website_id', '=', website_id), ('url', '=', ABOUT_URL)], limit=1)
    if not about_menu:
        about_menu = Menu.create({
            'name': ABOUT_NAMES['en_US'],
            'url': ABOUT_URL,
            'page_id': page.id,
            'parent_id': root.id,
            'website_id': website_id,
        })
        print('Created About menu')
    _write_translations(about_menu, 'name', ABOUT_NAMES)

    # --- Policies parent ----------------------------------------------
    policy_menus = Menu.search([
        ('website_id', '=', website_id),
        ('url', 'in', POLICY_URLS),
    ])
    if not policy_menus:
        print('! No policy menus found. Are the page URLs on this database '
              'the same as the ones listed in POLICY_URLS?')

    parent = Menu.search([
        ('website_id', '=', website_id),
        ('parent_id', '=', root.id),
        ('name', 'in', list(POLICY_NAMES.values())),
        ('url', 'in', (False, '#')),
    ], limit=1)
    if not parent:
        parent = Menu.create({
            'name': POLICY_NAMES['en_US'],
            # No page of its own: it exists to hold the submenu. Odoo renders
            # a menu without a real URL as a dropdown toggle.
            'url': '#',
            'parent_id': root.id,
            'website_id': website_id,
        })
        print('Created Policies menu')
    _write_translations(parent, 'name', POLICY_NAMES)

    # --- Move the policy entries under it ------------------------------
    by_url = {m.url: m for m in policy_menus}
    for index, url in enumerate(POLICY_URLS):
        menu = by_url.get(url)
        if not menu:
            print('  ! no menu for', url, '- skipped')
            continue
        menu.write({'parent_id': parent.id, 'sequence': index})
    print('Moved %s policy entries under the parent' % len(by_url))

    # --- Order the top level -------------------------------------------
    for index, url in enumerate(TOP_ORDER):
        menu = Menu.search([
            ('website_id', '=', website_id),
            ('parent_id', '=', root.id),
            ('url', '=', url),
        ], limit=1)
        if menu:
            menu.sequence = index
    parent.sequence = len(TOP_ORDER)

    env.cr.commit()

    # The running server caches the menu ids per website. Writing them marked
    # the cache dirty here, but only this call writes the sequence the other
    # processes poll on their next request.
    env.registry.clear_cache()
    env.registry.signal_changes()

    _print_tree(Menu, root, 'Top menu after:')
    print('\nDone. Reload the site; if the old bar is still there, restart Odoo.')


run()
