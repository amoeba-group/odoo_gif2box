from . import controllers
from . import models


def post_init_hook(env):
    """Give the order lines that exist already their review code: the
    thank-you card of an order placed before this module needs one too."""
    env['sale.order.line'].search([('g2b_review_code', '=', False)])._g2b_ensure_review_code()
