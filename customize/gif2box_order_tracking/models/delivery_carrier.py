from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    g2b_courier_name = fields.Char(
        string='Courier', default='Việt Tín',
        help="Who actually carries the parcels, as the customer is told on the "
             "tracking page and in the emails (\"Handed to Việt Tín\"). Empty, "
             "the delivery method's name is used.")

    def gif2box_distance_get_tracking_link(self, picking):
        """The courier's page for a parcel, from the method's "Tracking
        Link" (its `<shipmenttrackingnumber>` replaced), as Odoo does for
        its fixed-price methods."""
        if self.tracking_url and picking.carrier_tracking_ref:
            return self.tracking_url.replace('<shipmenttrackingnumber>', picking.carrier_tracking_ref)
        return False
