from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Ship this module's JavaScript translations to the website.

        The frontend only fetches translations for `web` and for modules
        whose name starts with `website` (see `website/models/ir_http.py`),
        so without this the dialog title patched in
        `static/src/js/product_configurator_title.js` would stay English on
        the Vietnamese, Japanese and Korean sites.
        """
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['gif2box_theme_home']

    @classmethod
    def _match(cls, path):
        """Pick a visitor's language from the browser the way it was meant.

        Odoo reads the browser's first choice of language only when it names
        a country ("vi-VN") or babel knows an alias for it, and "vi" has none.
        In every other case, a browser that sends no Accept-Language header
        included, it falls back to English rather than to the website's
        default language, so a Vietnamese visitor whose browser sends a bare
        "vi" was redirected to /en.

        For visitors not logged in, the context language the frontend
        routing reads (see `http_routing/models/ir_http.py`) is set to the
        browser's first choice as sent, or to nothing. The routing maps "vi"
        to vi_VN, and with nothing there it uses the website's default
        language. Bots, the language in the URL and the language picked in
        the language selector (its cookie) still take precedence.
        """
        if hasattr(request, 'is_frontend') or request.session.uid:
            return super()._match(path)
        context_lang = request.env.context.get('lang')
        request.update_context(lang=cls._gif2box_browser_lang())
        try:
            return super()._match(path)
        finally:
            if getattr(request, 'is_frontend', False) and getattr(request, 'lang', None):
                request.update_context(lang=request.lang.code)
            else:
                # Routes outside the website keep Odoo's choice.
                request.update_context(lang=context_lang)

    @classmethod
    def _gif2box_browser_lang(cls):
        """The browser's first choice as a language code ("vi", "vi_VN"),
        or None when it sends none."""
        best = request.httprequest.accept_languages.best
        if not best or best == '*':
            return None
        code, _, region = best.replace('-', '_').partition('_')
        return f'{code.lower()}_{region.upper()}' if region else code.lower()
