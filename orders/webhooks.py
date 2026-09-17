

import logging
 
import stripe
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
 
from .models import Order, Status
 
logger = logging.getLogger(__name__)
 
 
@csrf_exempt
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error('Stripe webhook called but STRIPE_WEBHOOK_SECRET is not set')
        return HttpResponseBadRequest('Webhook not configured.')

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
 
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning('Stripe webhook signature verification failed')
        return HttpResponseBadRequest('Invalid signature.')
 
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        _mark_paid(session)
 
    # Any 2xx tells Stripe not to retry. Unhandled event types are expected
    # and fine -- we only subscribed to what we act on, but Stripe may send
    # more depending on account-level settings.
    return HttpResponse(status=200)
 
 
def _mark_paid(session):
    session_id = session.get('id')
    order = Order.objects.filter(stripe_checkout_session_id=session_id).first()
 
    if order is None:
        # Shouldn't happen if start_checkout always saves the session id
        # before redirecting, but a webhook for an order we can't find
        # should never 500 -- log it and move on.
        logger.error('Stripe webhook: no Order for session %s', session_id)
        return
 
    if order.status == Status.PAID:
        return  # already processed, duplicate delivery -- no-op
 
    order.status = Status.PAID
    order.stripe_payment_intent_id = session.get('payment_intent', '')
    order.save(update_fields=['status', 'stripe_payment_intent_id'])
 
 
    logger.info('Stripe webhook: paid Order %s', order)