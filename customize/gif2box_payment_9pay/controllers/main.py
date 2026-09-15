# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.amb_payment_9pay.controllers import main

_logger = logging.getLogger(__name__)


class NinePayController(main.NinePayController):
    """Project-specific fixes for the 9Pay controller."""

    @http.route()
    def ninepay_ipn(self, **post):
        """Handle the server-to-server IPN sent by 9Pay.

        Overridden to look the transaction up on ``payment.transaction``. The
        base implementation searched ``payment.provider``, which has neither a
        ``reference`` nor a ``provider_code`` field, so every IPN call raised
        before the payment could be confirmed.
        """
        result = post.get('result')
        checksum = post.get('checksum')

        if not result or not checksum:
            _logger.warning('[9Pay] IPN missing result or checksum')
            return json.dumps({'error_code': '99', 'error_des': 'Invalid data'})

        # Find provider
        provider = request.env['payment.provider'].sudo().search([
            ('code', '=', 'ninepay'),
            ('state', 'in', ['enabled', 'test'])
        ], limit=1)

        if not provider or not provider.ninepay_checksum_key:
            _logger.error('[9Pay] IPN - Provider not found or checksum key missing')
            return json.dumps({'error_code': '99', 'error_des': 'Provider configuration error'})

        # Verify checksum
        _logger.info('[9Pay] IPN - Verifying checksum...')
        if not self._verify_checksum(result, checksum, provider.ninepay_checksum_key):
            _logger.error('[9Pay] IPN - Checksum verification FAILED')
            return json.dumps({'error_code': '99', 'error_des': 'Invalid checksum'})

        _logger.info('[9Pay] IPN - Checksum verification OK')

        # Decode result
        try:
            decoded_json = self._safe_base64_decode(result)
            decoded = json.loads(decoded_json)

            _logger.info('[9Pay] IPN - Decoded result: %s', decoded)

            reference = decoded.get('invoice_no')

            if not reference:
                _logger.error('[9Pay] IPN - Missing invoice_no')
                return json.dumps({'error_code': '99', 'error_des': 'Missing invoice_no'})

        except Exception as e:
            _logger.error('[9Pay] IPN - Error decoding result: %s', e, exc_info=True)
            return json.dumps({'error_code': '99', 'error_des': 'Invalid result format'})

        # Find transaction
        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'ninepay')
        ], limit=1)

        if not tx:
            _logger.warning('[9Pay] IPN - No transaction found for: %s', reference)
            return json.dumps({'error_code': '99', 'error_des': 'Transaction not found'})

        _logger.info('[9Pay] IPN - Found transaction %s (state: %s)', tx.reference, tx.state)

        if tx.state in ['done', 'cancel']:
            _logger.info('[9Pay] IPN - Already processed (state: %s)', tx.state)
            return json.dumps({'error_code': '00', 'error_des': 'Already processed'})

        try:
            tx._handle_notification_data('ninepay', post)
            _logger.info('[9Pay] IPN - Processed successfully - State: %s', tx.state)
            return json.dumps({'error_code': '00', 'error_des': 'Success'})
        except Exception as e:
            _logger.error('[9Pay] IPN - Processing error: %s', e, exc_info=True)
            return json.dumps({'error_code': '99', 'error_des': 'Processing error'})
