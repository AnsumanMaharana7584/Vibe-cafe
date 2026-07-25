import os
from uuid import uuid4

PHONEPE_CLIENT_ID = os.environ.get("PHONEPE_CLIENT_ID", "")
PHONEPE_CLIENT_SECRET = os.environ.get("PHONEPE_CLIENT_SECRET", "")
PHONEPE_CLIENT_VERSION = int(os.environ.get("PHONEPE_CLIENT_VERSION", "1"))
PHONEPE_ENV = os.environ.get("PHONEPE_ENV", "SANDBOX").upper()
PHONEPE_CALLBACK_USERNAME = os.environ.get("PHONEPE_CALLBACK_USERNAME", "")
PHONEPE_CALLBACK_PASSWORD = os.environ.get("PHONEPE_CALLBACK_PASSWORD", "")

_phonepe_client = None

try:
    from phonepe.sdk.pg.env import Env
    from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
    from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest
    from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo
    from phonepe.sdk.pg.payments.v2.models.request.prefill_user_login_details import PrefillUserLoginDetails
    PHONEPE_SDK_AVAILABLE = True
except ImportError:
    Env = None
    StandardCheckoutClient = None
    StandardCheckoutPayRequest = None
    MetaInfo = None
    PrefillUserLoginDetails = None
    PHONEPE_SDK_AVAILABLE = False


def is_phonepe_enabled():
    return bool(
        PHONEPE_SDK_AVAILABLE
        and PHONEPE_CLIENT_ID
        and PHONEPE_CLIENT_SECRET
    )


def get_phonepe_env():
    if PHONEPE_ENV == "PRODUCTION":
        return Env.PRODUCTION
    return Env.SANDBOX


def get_phonepe_client():
    global _phonepe_client
    if not is_phonepe_enabled():
        return None
    if _phonepe_client is None:
        _phonepe_client = StandardCheckoutClient.get_instance(
            client_id=PHONEPE_CLIENT_ID,
            client_secret=PHONEPE_CLIENT_SECRET,
            client_version=PHONEPE_CLIENT_VERSION,
            env=get_phonepe_env(),
            should_publish_events=False,
        )
    return _phonepe_client


def build_merchant_order_id(order_id):
    return f"VC-{order_id}-{uuid4().hex[:8]}"


def initiate_payment(order, redirect_url):
    client = get_phonepe_client()
    merchant_order_id = build_merchant_order_id(order.id)
    amount_paise = max(int(round(order.total * 100)), 100)

    prefill = PrefillUserLoginDetails(phone_number=order.customer_phone)
    meta_info = MetaInfo(
        udf1=str(order.id),
        udf2=order.customer_name,
        udf3=order.customer_email,
    )

    pay_request = StandardCheckoutPayRequest.build_request(
        merchant_order_id=merchant_order_id,
        amount=amount_paise,
        redirect_url=redirect_url,
        meta_info=meta_info,
        prefill_user_login_details=prefill,
        message=f"Vibe Cafe order #{order.id}",
        expire_after=3600,
    )
    response = client.pay(pay_request)
    return merchant_order_id, response


def get_payment_status(merchant_order_id):
    client = get_phonepe_client()
    return client.get_order_status(merchant_order_id, details=False)


def validate_webhook(authorization_header, body):
    if not PHONEPE_CALLBACK_USERNAME or not PHONEPE_CALLBACK_PASSWORD:
        return None
    client = get_phonepe_client()
    return client.validate_callback(
        username=PHONEPE_CALLBACK_USERNAME,
        password=PHONEPE_CALLBACK_PASSWORD,
        callback_header_data=authorization_header,
        callback_response_data=body,
    )
