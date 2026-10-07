import re
import unicodedata

from odoo import fields, models

# "Phường", "Xã", "Đặc khu", and the "TP" Odoo puts in front of four of the
# centrally-run cities. Sorting on what follows them is what makes a long
# list scannable: otherwise every ward files under P or X, and Hồ Chí Minh
# files under T.
_PREFIX = re.compile(r'^(Thành phố|Tỉnh|TP\.?|Phường|Xã|Đặc khu)\s+', re.IGNORECASE)


def vn_sort_key(name):
    """Order Vietnamese place names the way a reader looks for them.

    The prefix is dropped and so are the diacritics, so that "Đà Nẵng" sits
    among the Ds and "Ẩn" next to "An". The database collation here is `C`,
    which would put every Đ after Z.
    """
    name = _PREFIX.sub('', name or '').replace('Đ', 'D').replace('đ', 'd')
    name = unicodedata.normalize('NFD', name)
    return ''.join(c for c in name if not unicodedata.combining(c)).casefold()


class ResCountryWard(models.Model):
    """The commune level of a Vietnamese address: phường, xã or đặc khu.

    Since 1 July 2025 Vietnam has two administrative levels, the province
    and the commune; districts were abolished. So a ward hangs directly off
    a `res.country.state`, and an address needs nothing in between.
    """
    _name = 'res.country.ward'
    _description = 'Ward / Commune'
    _order = 'state_id, name'
    _rec_names_search = ['name', 'code']

    name = fields.Char(string='Name', required=True)
    code = fields.Char(
        string='GSO code', required=True, index=True,
        help="Code of the unit in the General Statistics Office register.")
    division_type = fields.Selection(
        selection=[('phuong', 'Ward'), ('xa', 'Commune'), ('dac_khu', 'Special zone')],
        string='Type', required=True)
    state_id = fields.Many2one(
        'res.country.state', string='Province / City', required=True, index=True,
        ondelete='cascade')
    country_id = fields.Many2one(
        related='state_id.country_id', string='Country', store=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Each ward has its own GSO code.'),
    ]

    def _sorted_for_display(self):
        return self.sorted(key=lambda ward: vn_sort_key(ward.name))
