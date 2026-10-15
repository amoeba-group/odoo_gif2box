import base64
import binascii
import json
import logging

from odoo import api, fields, models
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL
from odoo.tools.image import image_data_uri, image_process

_logger = logging.getLogger(__name__)

# The words a visitor reads, translated together.
TRANSLATED_FIELDS = ('title', 'description', 'button_text')

# Odoo's own AI text service, the one behind the editor's "AI" command: no key
# to set up, and the endpoint can be moved by the same system parameter.
OLG_ENDPOINT = 'https://olg.api.odoo.com'


class WebsiteHeroBanner(models.Model):
    """One slide of the hero at the top of the homepage.

    The banners this replaces had their headline and their "Shop now" button
    painted into the picture: changing a word meant redrawing the image, the
    button could not be clicked, and nothing could be translated.

    A slide is built from two layers, as those banners were drawn: a
    background that runs edge to edge, and in front of it, held to the width
    of the page, the product picture on one side and the words on the other.
    """
    _name = 'website.hero.banner'
    _description = 'Homepage Hero Banner'
    _order = 'sequence, id'

    name = fields.Char(
        string='Internal name', required=True,
        help="Only shown here, to tell the banners apart.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    website_id = fields.Many2one(
        'website', string='Website', ondelete='cascade',
        help="Leave empty to show the banner on every website.")

    # Help texts are kept to one literal each: Odoo's term extractor does not
    # join adjacent string literals, and would miss them for translation.
    image_desktop = fields.Image(
        string='Background image', required=True, max_width=2560, max_height=2560,
        help="Runs the full width of the screen, behind everything. Best at 1920 x 528 px. Keep it calm, a colour wash or a soft scene: the product and the text sit on top of it.")
    image_mobile = fields.Image(
        string='Mobile background', max_width=1440, max_height=1440,
        help="Optional. Shown on phones instead of the wide background, which would otherwise be cropped. Best at 1080 x 1350 px.")
    image_product = fields.Image(
        string='Product image', max_width=1600, max_height=1600,
        help="The product, on a transparent background (PNG or WebP), shown beside the text within the page width. Best at about 1200 x 1000 px. Not shown when the text is centred.")

    # Text rather than Char so the title can be broken where it should be,
    # as the artwork breaks it: Enter in the form is a new line on the page.
    title = fields.Text(
        string='Title', translate=True,
        help="Press Enter to choose where the title breaks onto a new line.")
    description = fields.Text(string='Description', translate=True)
    button_text = fields.Char(
        string='Button text', translate=True,
        default=lambda self: self.env._("Shop now"))
    button_url = fields.Char(
        string='Button link',
        help="Page the button opens, e.g. /shop/category/gift-38 or a full address. With a link but no button text, the whole banner is clickable.")

    content_position = fields.Selection(
        selection=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')],
        string='Text position', required=True, default='right',
        help="The product image takes the other side.")
    text_theme = fields.Selection(
        selection=[('dark', 'Dark text'), ('light', 'Light text')],
        string='Text colour', required=True, default='dark',
        help="Dark text for light pictures, light text for dark ones.")
    title_style = fields.Selection(
        selection=[('serif', 'Serif'), ('sans', 'Sans-serif')],
        string='Title style', required=True, default='serif',
        help="Serif for an elegant, gift-like title; sans-serif to match the rest of the site.")

    preview_html = fields.Html(
        string='Preview', compute='_compute_preview_html', sanitize=False)

    # --- Translation -------------------------------------------------------
    #
    # The words are typed once, in any of the website's languages, and the
    # other languages are filled in by machine on saving. What the machine
    # wrote is remembered, so a translation corrected by hand is told apart
    # and never written over.
    auto_translate = fields.Boolean(
        string='Translate automatically', default=True,
        help="On saving, the title, description and button text are translated into the website's other languages. Translations corrected by hand are kept.")
    translation_source_lang = fields.Char(
        string='Original language', readonly=True,
        help="The language the words were written in, as detected on the last translation.")
    machine_translations = fields.Json(
        string='Machine translations', readonly=True,
        help="What the machine wrote for each language, to tell its translations from those corrected by hand.")
    # The words of every language, edited together in a table on the form.
    translation_values = fields.Json(
        string='Translations', compute='_compute_translation_values',
        inverse='_inverse_translation_values', readonly=False)

    # --- Preview -----------------------------------------------------------

    @api.depends('image_desktop', 'image_product', 'title', 'description', 'button_text',
                 'content_position', 'text_theme', 'title_style')
    def _compute_preview_html(self):
        """Render the banner as the homepage will, so it can be judged here.

        Recomputed on every change in the form, before saving. The picture is
        inlined at reduced size: a new one has no URL yet.
        """
        for banner in self:
            banner.preview_html = self.env['ir.qweb']._render(
                'gif2box_hero_banner.hero_banner_preview',
                {
                    'banner': banner,
                    'image_src': banner._gif2box_preview_image_src('image_desktop', 960),
                    'product_src': banner._gif2box_preview_image_src('image_product', 480),
                },
            )

    def _gif2box_preview_image_src(self, field, width):
        """One of the banner's pictures, for the preview.

        A picture already saved is given by URL: the browser caches it, and
        the preview is re-sent on every change in the form. Only one just
        uploaded and not yet saved has no URL, and is inlined, reduced; a
        transparent product PNG inlined every time came to over 300 KB.

        Read with `bin_size` off: the web client opens forms with it on, and an
        image field then answers with its size ("49.90 Kb") instead of the
        picture.
        """
        self.ensure_one()
        raw = self.with_context(bin_size=False)[field]
        if not raw:
            return False
        origin = self._origin
        size = '%sx0' % width
        if origin.id and raw == origin.with_context(bin_size=False)[field]:
            return self.env['website'].image_url(origin, field, size=size)
        try:
            small = image_process(base64.b64decode(raw), size=(width, 0))
            return image_data_uri(base64.b64encode(small))
        except (binascii.Error, ValueError, UserError):
            return origin.id and self.env['website'].image_url(origin, field, size=size)

    # --- Translation -------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        banners = super().create(vals_list)
        if not self.env.context.get('gif2box_hero_no_translate'):
            for banner, vals in zip(banners, vals_list):
                if banner.auto_translate:
                    banner._gif2box_translate(changed=set(vals) & set(TRANSLATED_FIELDS))
        return banners

    def write(self, vals):
        if self.env.context.get('gif2box_hero_no_translate') or not (
                set(vals) & set(TRANSLATED_FIELDS) or vals.get('auto_translate')):
            return super().write(vals)
        # The words as they were, in the language being written: a language
        # still showing them was never translated, and must follow the change.
        before = {
            banner.id: {fname: banner[fname] for fname in TRANSLATED_FIELDS}
            for banner in self
        }
        result = super().write(vals)
        for banner in self.filtered('auto_translate'):
            # Only what really changed: after a translation is set, as from
            # the translation dialog, Odoo writes the field again with the
            # value it already has.
            changed = {
                fname for fname in TRANSLATED_FIELDS
                if fname in vals and (vals[fname] or False) != (before[banner.id][fname] or False)
            }
            if changed or vals.get('auto_translate'):
                banner._gif2box_translate(old_texts=before[banner.id], changed=changed)
        return result

    def _gif2box_languages(self):
        """The languages of the website(s) the banner shows on."""
        self.ensure_one()
        websites = self.website_id or self.env['website'].sudo().search([])
        return websites.language_ids or self.env['res.lang'].search([('code', '=', self.env.lang)])

    def _gif2box_stored_texts(self):
        """Each translated field as stored, by language, without fallback.

        The ORM answers a language with no translation of its own with the
        English text; here a missing language stays missing.
        """
        self.ensure_one()
        self.flush_recordset(list(TRANSLATED_FIELDS))
        self.env.cr.execute(SQL(
            "SELECT %s FROM %s WHERE id = %s",
            SQL(', ').join(SQL.identifier(fname) for fname in TRANSLATED_FIELDS),
            SQL.identifier(self._table), self.id,
        ))
        row = self.env.cr.fetchone() or (None,) * len(TRANSLATED_FIELDS)
        return {fname: dict(value or {}) for fname, value in zip(TRANSLATED_FIELDS, row)}

    def _gif2box_default_lang(self):
        """The language of the original words: as detected, else the website's."""
        self.ensure_one()
        website = self.website_id or self.env['website'].get_current_website()
        return self.translation_source_lang or website.default_lang_id.code or self.env.lang

    def _gif2box_translate(self, old_texts=None, overwrite=False, raise_errors=False, changed=()):
        """Fill in the other languages from the original words.

        `changed` names the fields just written, in the language of the
        context. Written in the original language, they are the new original.
        Written in another language, they are asked about: still in the
        original language (Vietnamese typed by a user working in English),
        they are the new original all the same, and go to its place; in the
        language of the form, they correct that language's translation, and
        are kept as they are.

        A language is translated when it has nothing or still shows the
        original's words; and when the original just changed, if it shows
        the words as they were or what the machine last wrote for it.
        Anything else was corrected by hand and is kept, unless `overwrite`
        asks for everything to be done again.

        Saving never fails because the service is out of reach: the banner is
        saved untranslated, and the form says which languages are missing.
        """
        done = self.browse()
        for banner in self:
            written_lang = banner.env.lang
            original_lang = banner._gif2box_default_lang()
            stored = banner._gif2box_stored_texts()
            written = banner.with_context(lang=written_lang)
            typed = {fname: written[fname] for fname in changed if written[fname]}
            langs = banner._gif2box_languages()
            try:
                if typed and written_lang != original_lang:
                    detected = banner._gif2box_ai_detect(typed, (original_lang, written_lang))
                    if all(code == written_lang for code in detected.values()) and not any(
                            stored[fname].get(original_lang) for fname in TRANSLATED_FIELDS
                            if fname not in typed):
                        # A new banner written in the language of the form.
                        original_lang = written_lang
                    else:
                        typed = {fname: text for fname, text in typed.items()
                                 if detected.get(fname) != written_lang}
                texts = {}
                for fname in TRANSLATED_FIELDS:
                    value = typed.get(fname) or (
                        None if fname in changed else stored[fname].get(original_lang))
                    if value:
                        texts[fname] = value
                machine = dict(banner.machine_translations or {})
                old_texts = old_texts or {}

                def needed(code, fname):
                    # Missing, or still the original's words: always. The
                    # machine's own work: only once the original changed,
                    # or every save would reword it.
                    value = stored[fname].get(code)
                    return overwrite or not value or value == texts[fname] or (
                        fname in typed and value in (
                            old_texts.get(fname), stored[fname].get(original_lang),
                            (machine.get(code) or {}).get(fname)))

                todo = {
                    lang.code: [fname for fname in texts if needed(lang.code, fname)]
                    for lang in langs if lang.code != original_lang
                }
                todo = {code: fnames for code, fnames in todo.items() if fnames}
                translated = banner._gif2box_ai_translate(
                    {fname: texts[fname] for fname in set().union(*todo.values())},
                    original_lang, langs.filtered(lambda lang: lang.code in todo),
                ) if todo else {}
            except (AccessError, UserError, ValueError) as error:
                if raise_errors:
                    raise UserError(self.env._(
                        "The banner could not be translated: %(error)s",
                        error=getattr(error, 'args', [error])[0] or error)) from error
                _logger.warning("Hero banner %s left untranslated: %s", banner.id, error)
                continue

            updates = {fname: {} for fname in TRANSLATED_FIELDS}
            for fname, text in typed.items():
                if written_lang != original_lang:
                    # Typed in another language's place: the original takes it.
                    updates[fname][original_lang] = text
            for code, fnames in todo.items():
                for fname in fnames:
                    value = (translated.get(code) or {}).get(fname)
                    if value:
                        updates[fname][code] = value
                        machine.setdefault(code, {})[fname] = value
            machine.pop(original_lang, None)
            for fname, values in updates.items():
                if values:
                    banner.with_context(gif2box_hero_no_translate=True) \
                        .update_field_translations(fname, values)
            banner.with_context(gif2box_hero_no_translate=True).write({
                'machine_translations': {code: values for code, values in machine.items() if values},
                'translation_source_lang': original_lang,
            })
            if any(updates.values()):
                done |= banner
        return done

    def _gif2box_ai_translate(self, texts, source_lang, langs):
        """The words, in the original language, in each of `langs`."""
        if not texts or not langs:
            return {}
        names = {lang.code: lang.name for lang in langs}
        source_name = self._gif2box_lang_name(source_lang)
        answer = self._gif2box_ai_ask("\n".join([
            "You translate the homepage banner of gif2box, a Vietnamese shop for baby and mother gift boxes.",
            "Translate the texts below from %s into: %s." % (
                source_name, ", ".join("%s (code %s)" % (name, code) for code, name in names.items())),
            "Translate the meaning, not word for word: short, warm and natural, as a native marketer would write a headline."
            " Add nothing and leave nothing out. Keep the brand and product names."
            " Keep every line break (\\n) where the original has one, and the same number of lines.",
            'Answer with JSON only, shaped {"<code>": {"<key>": "<text>"}}, with the same keys as the texts.',
            "Texts:",
            json.dumps(texts, ensure_ascii=False),
        ]))
        return {
            code: {fname: str(value).strip() for fname, value in (values or {}).items()
                   if fname in texts and value}
            for code, values in answer.items() if code in names and isinstance(values, dict)
        }

    def _gif2box_ai_detect(self, texts, codes):
        """For each text, which of the two languages it is written in.

        Asked apart from the translation, and between two languages only:
        asked about several texts and every language at once, the machine
        took "Shop the combo" for Vietnamese.
        """
        names = {code: self._gif2box_lang_name(code) for code in codes}
        answer = self._gif2box_ai_ask("\n".join([
            "For each text below, say whether it is written in %s." % " or in ".join(
                "%s (code %s)" % (name, code) for code, name in names.items()),
            "Judge each text on its own words only. Vietnamese written without accents is still Vietnamese.",
            'Answer with JSON only, shaped {"<key>": "<code>"}, with the same keys as the texts.',
            "Texts:",
            json.dumps(texts, ensure_ascii=False),
        ]))
        return {fname: code for fname, code in answer.items() if fname in texts and code in names}

    def _gif2box_lang_name(self, code):
        lang = self.env['res.lang'].with_context(active_test=False).search([('code', '=', code)], limit=1)
        return lang.name or code

    def _gif2box_ai_ask(self, prompt):
        """Odoo's AI text service: the answer, read as JSON."""
        ICP = self.env['ir.config_parameter'].sudo()
        response = iap_tools.iap_jsonrpc(
            ICP.get_param('web_editor.olg_api_endpoint', OLG_ENDPOINT) + '/api/olg/1/chat',
            params={
                'prompt': prompt,
                'conversation_history': [],
                'database_id': ICP.get_param('database.uuid'),
            },
            timeout=45,
        )
        status = response.get('status')
        if status == 'limit_call_reached':
            raise UserError(self.env._("The translation service has reached its limit for now. Try again later."))
        if status != 'success':
            raise UserError(self.env._("The translation service did not answer. Try again later."))
        content = response.get('content') or ''
        # The answer may come wrapped in a code block.
        answer = json.loads(content[content.find('{'):content.rfind('}') + 1])
        if not isinstance(answer, dict):
            raise ValueError("Unexpected answer from the translation service")
        return answer

    # No dependencies on purpose: computed when the form is read, and left
    # alone while it is edited, or typing in the Title field would throw away
    # what was typed in the table.
    @api.depends()
    def _compute_translation_values(self):
        """Each language's words as saved, and where they came from.

        Each row carries the words twice, `values` to edit and `initial` as
        they were read, so that saving writes only what was changed.
        """
        for banner in self:
            origin = banner._origin
            rows = []
            if origin.id:
                stored = origin._gif2box_stored_texts()
                machine = origin.machine_translations or {}
                source = origin._gif2box_default_lang()
                langs = origin._gif2box_languages().sorted(lambda lang: lang.code != source)
                originals = {fname: stored[fname].get(source) for fname in TRANSLATED_FIELDS}
                for lang in langs:
                    values = {fname: stored[fname].get(lang.code) for fname in TRANSLATED_FIELDS}
                    filled = [fname for fname in TRANSLATED_FIELDS if values[fname]]
                    if lang.code == source:
                        state = 'source'
                    elif not filled or any(
                            not values[fname] for fname in TRANSLATED_FIELDS if originals.get(fname)
                    ) or all(values[fname] == originals[fname] for fname in filled):
                        state = 'missing'
                    elif any(values[fname] != (machine.get(lang.code) or {}).get(fname) for fname in filled):
                        state = 'manual'
                    else:
                        state = 'machine'
                    texts = {fname: values[fname] or '' for fname in TRANSLATED_FIELDS}
                    rows.append({
                        'code': lang.code,
                        # In its own name ("Japanese / 日本語" reads 日本語):
                        # understood whatever the admin's language.
                        'name': lang.name.split(' / ')[-1],
                        'state': state,
                        'values': texts,
                        'initial': dict(texts),
                    })
            banner.translation_values = {'rows': rows}

    def _inverse_translation_values(self):
        """Save the cells changed in the table.

        A translation is set as typed, and from then on counts as corrected by
        hand. A change to the original is written as any change to it is, so
        the other languages follow.
        """
        for banner in self:
            originals = {}
            original_lang = banner._gif2box_default_lang()
            for row in (banner.translation_values or {}).get('rows') or []:
                code = row.get('code')
                values, initial = row.get('values') or {}, row.get('initial') or {}
                changed = {
                    fname: values.get(fname) or ''
                    for fname in TRANSLATED_FIELDS
                    if (values.get(fname) or '') != (initial.get(fname) or '')
                }
                if not changed or code not in banner._gif2box_languages().mapped('code'):
                    continue
                if code == original_lang:
                    originals = changed
                    continue
                for fname, value in changed.items():
                    banner.with_context(gif2box_hero_no_translate=True) \
                        .update_field_translations(fname, {code: value or False})
            # Last, so that the languages just corrected count as such.
            if originals:
                banner.with_context(lang=original_lang).write(originals)
        # Read afresh after saving, not as typed.
        self.invalidate_recordset(['translation_values'])

    def action_translate(self):
        """Translate the languages not corrected by hand."""
        return self._gif2box_translate_action(overwrite=False)

    def action_translate_all(self):
        """Translate every language again, hand corrections included."""
        return self._gif2box_translate_action(overwrite=True)

    def _gif2box_translate_action(self, overwrite):
        self.ensure_one()
        original = self.with_context(lang=self._gif2box_default_lang())
        if not any(original[fname] for fname in TRANSLATED_FIELDS):
            raise UserError(self.env._("Write a title, a description or a button text first."))
        done = self._gif2box_translate(overwrite=overwrite, raise_errors=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if done else 'info',
                'message': self.env._("Translations updated.") if done
                    else self.env._("Every language is already translated."),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # --- Actions -----------------------------------------------------------

    def action_view_on_website(self):
        self.ensure_one()
        website = self.website_id or self.env['website'].get_current_website()
        return {
            'type': 'ir.actions.act_url',
            'url': website.homepage_url or '/',
            'target': 'new',
        }

    # --- Rendering helpers -------------------------------------------------

    def _gif2box_link_whole_slide(self):
        """A link but no button text: the slide itself is what is clicked."""
        self.ensure_one()
        return bool(self.button_url) and not self.button_text

    def _gif2box_show_button(self):
        self.ensure_one()
        return bool(self.button_url and self.button_text)

    def _gif2box_show_product(self):
        """The product image needs a side of its own, so not with centred text."""
        self.ensure_one()
        return bool(self.image_product) and self.content_position != 'center'
