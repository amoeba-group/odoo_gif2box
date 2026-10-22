from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The starter posts came out in English and Vietnamese, with only their
    titles in Japanese and Korean; write them again in every language."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['blog.blog']._gif2box_refresh_starter_posts()
