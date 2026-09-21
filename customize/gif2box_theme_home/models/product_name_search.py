"""Search product names across every language, not just the current one.

`name` on `product.template` is a translated field: Odoo stores it as a jsonb
column keyed by language, and `_field_to_sql` narrows a condition on it down to
the language in the request plus its fallback --

    COALESCE(name->>'vi_VN', name->>'en_US') ILIKE '%...%'

-- so an administrator working in Vietnamese who types a Japanese or Korean
product name gets nothing back, even though the name is right there in the
same row.

The override below matches against every translation the row holds, using the
expression Odoo already builds for its own trigram prefilter:

    jsonb_path_query_array(name, '$.*')::text ILIKE '%...%'

It is scoped to `like`-family operators on `name`. Everything else -- `=`,
`in`, sorting, any other field -- goes to `super()` untouched, so nothing that
relies on exact per-language matching changes behaviour.

This sits below the search views rather than in them, so it covers the Products
list, the Product Variants list, the many2one autocompletes and the shop search
in one place.
"""

from odoo import models
from odoo.tools import SQL

# The operators where a cross-language match is what someone means. `=` and
# `in` are deliberately absent: those ask about one specific value.
_LIKE_OPERATORS = ('like', 'ilike', 'not like', 'not ilike', '=like', '=ilike')


def _all_languages_sql(record, alias, fname, operator, value, query):
    """Return SQL matching `value` against every translation of `fname`.

    Returns None when the field is not a stored translated column, so the
    caller can fall back to the standard behaviour.
    """
    field = record._fields[fname]
    model = record

    # On `product.product` the name is inherited from the template, so the
    # column lives on another table and the query needs the join Odoo would
    # have added itself.
    if field.related and not field.store:
        model, field, alias = record._traverse_related_sql(alias, field, query)

    if not field.translate or not field.store:
        return None

    column = SQL('%s.%s', SQL.identifier(alias), SQL.identifier(field.name))
    # `'$.*'` is every value in the jsonb object, one per language; `::text`
    # renders them as a JSON array literal, which a LIKE can scan in one go.
    all_langs = record.pool.unaccent(
        SQL("jsonb_path_query_array(%s, '$.*')::text", column))

    # `=like` and `=ilike` take the pattern as given; the others wrap it.
    pattern = value if operator.startswith('=') else f'%{value}%'
    sql_pattern = record.pool.unaccent(SQL('%s', pattern))

    case_sensitive = 'ilike' not in operator
    sql_operator = SQL('LIKE') if case_sensitive else SQL('ILIKE')

    condition = SQL('%s %s %s', all_langs, sql_operator, sql_pattern)
    if operator.startswith('not '):
        # A row with no name at all must come back for a negative match, the
        # way it does for the stock condition.
        return SQL('(NOT (%s) OR %s IS NULL)', condition, column)
    return condition


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _condition_to_sql(self, alias, fname, operator, value, query):
        if fname == 'name' and operator in _LIKE_OPERATORS and isinstance(value, str) and value:
            sql = _all_languages_sql(self, alias, fname, operator, value, query)
            if sql is not None:
                return sql
        return super()._condition_to_sql(alias, fname, operator, value, query)


class ProductProduct(models.Model):
    # `product.product` delegates to the template through `_inherits`, which
    # means a Python override on `product.template` does not reach it: the two
    # are separate classes. The variants list needs its own.
    _inherit = 'product.product'

    def _condition_to_sql(self, alias, fname, operator, value, query):
        if fname == 'name' and operator in _LIKE_OPERATORS and isinstance(value, str) and value:
            sql = _all_languages_sql(self, alias, fname, operator, value, query)
            if sql is not None:
                return sql
        return super()._condition_to_sql(alias, fname, operator, value, query)
