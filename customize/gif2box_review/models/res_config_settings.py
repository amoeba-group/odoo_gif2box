from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # "Moderate", not "publish right away": a Boolean setting stored as a
    # system parameter is deleted when switched off, so the parameter must
    # mean the exception. Unset, reviews are published as they come.
    g2b_review_moderate = fields.Boolean(
        string='Approve Reviews First',
        config_parameter='gif2box_review.moderate',
        help="Off: a review shows on the product page as soon as it is written; the shop "
             "can still hide it. On: it waits until the shop publishes it.")
