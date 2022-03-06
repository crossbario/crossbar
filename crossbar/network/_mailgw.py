# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import re
import requests

from cfxdb.xbrnetwork import VerificationType

_USERNAME_PAT_STR = r'^[a-z][a-z0-9_]{4,14}$'

_USERNAME_PAT = re.compile(_USERNAME_PAT_STR)

_ONBOARD_MEMBER_LOG_VERIFICATION_CODE_START = '>>>>> ONBOARD_MEMBER_VERIFICATION_CODE_START >>>>>'

_ONBOARD_MEMBER_LOG_VERIFICATION_CODE_END = '<<<<< ONBOARD_MEMBER_VERIFICATION_CODE_END <<<<<'

_ONBOARD_VERIFICATION_EMAIL_TITLE = "XBR Network: confirm account creation"

_ONBOARD_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request to create a user account
using your email address ({member_email}).

To continue creating an account using this email address, visit the
following link in the browser you used to start the action

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}

or complete the on-boarding using the CLI with this verification code

xbrnetwork --url <URL> register-member-verify --vaction={vaction_oid} --vcode={vaction_code}

If you did not receive this email before {expiration_date} or
you wish to create an account using a different email address you can begin
again by going to:

{website_url}/register

PRIVACY NOTICE: XBR Network is an open decentralized data exchange. Activity
on most of XBR Network, including email addresses, will be visible to the public.
We recommend using a secondary account or free web email service (such as Gmail, Yahoo,
Hotmail, or similar) to avoid receiving spam at your primary email address.

If you do not wish to create an account, or if this request was made in
error you can do nothing or visit the following link:

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&cancel=true

If the above links do not work, or you have any other issues regarding
your account, please contact administration at {operator_email}.
"""

_LOGIN_MEMBER_LOG_VERIFICATION_CODE_START = '>>>>> LOGIN_MEMBER_VERIFICATION_CODE_START >>>>>'

_LOGIN_MEMBER_LOG_VERIFICATION_CODE_END = '<<<<< LOGIN_MEMBER_VERIFICATION_CODE_END <<<<<'

_LOGIN_VERIFICATION_EMAIL_TITLE = "XBR Network: confirm login"

_LOGIN_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request to login as your user account from a new device.

To continue to log in from the device, visit the following link in the browser you used to start the action!

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}

or complete the login using the CLI with this verification code

xbrnetwork --url <URL> login-member-verify --vaction={vaction_oid} --vcode={vaction_code}
"""

_SIGNUP_TO_LOGIN_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request to create a user account
signed by your ethereum wallet with the following address

{wallet_address}

Since you already have an account we are sending you the login link instead

To continue to log in from the device, visit the following link in the browser you used to start the action!

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}&was_signup=1

or complete the login using the CLI with this verification code

xbrnetwork --url <URL> login-member-verify --vaction={vaction_oid} --vcode={vaction_code}
"""

_ACCOUNT_EXISTS_EMAIL_TITLE = "XBR Network: account already exists"

_ACCOUNT_EXISTS_EMAIL_BODY = """
XBR Network has received a request to create a user account
signed by ethereum wallet with the following address

{address_used}

However it seems your email address ({email}) is already registered
on XBR Network using the following address

{address_associated}

Kindly use the correct email and wallet address combination to login
to XBR Network.

Go to login page: {website_url}/login
"""

_CREATE_MARKET_LOG_VERIFICATION_CODE_START = '>>>>> CREATE_MARKET_VERIFICATION_CODE_START >>>>>'

_CREATE_MARKET_LOG_VERIFICATION_CODE_END = '<<<<< CREATE_MARKET_VERIFICATION_CODE_END <<<<<'

_CREATE_MARKET_VERIFICATION_EMAIL_TITLE = "XBR Network: confirm market creation"

_CREATE_MARKET_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request to create a data market.

To complete this, please open the following link in the browser you used to start the action!

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}
"""

_JOIN_MARKET_LOG_VERIFICATION_CODE_START = '>>>>> JOIN_MARKET_VERIFICATION_CODE_START >>>>>'

_JOIN_MARKET_LOG_VERIFICATION_CODE_END = '<<<<< JOIN_MARKET_VERIFICATION_CODE_END <<<<<'

_JOIN_MARKET_VERIFICATION_EMAIL_TITLE = "XBR Network: confirm joining market {market_id}"

_JOIN_MARKET_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request for you ({member_id}) to join a data market {market_id} with roles {roles}.

To complete this, please open the following link in the browser you used to start the action!

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}
"""

_CREATE_CATALOG_LOG_VERIFICATION_CODE_START = '>>>>> CREATE_CATALOG_VERIFICATION_CODE_START >>>>>'

_CREATE_CATALOG_LOG_VERIFICATION_CODE_END = '<<<<< CREATE_CATALOG_VERIFICATION_CODE_END <<<<<'

_CREATE_CATALOG_VERIFICATION_EMAIL_TITLE = "XBR Network: confirm catalog creation {catalog_id}"

_CREATE_CATALOG_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request for you ({member_id}) to create an api catalog {catalog_id}.

To complete this, please open the following link in the browser you used to start the action!

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}
"""

_PUBLISH_API_LOG_VERIFICATION_CODE_START = '>>>>> PUBLISH_API_VERIFICATION_CODE_START >>>>>'

_PUBLISH_API_LOG_VERIFICATION_CODE_END = '<<<<< PUBLISH_API_VERIFICATION_CODE_END <<<<<'

_PUBLISH_API_VERIFICATION_EMAIL_TITLE = "XBR Network: confirm catalog creation {catalog_id}"

_PUBLISH_API_VERIFICATION_EMAIL_BODY = """
XBR Network has received a request for you ({member_id}) to publish an api {api_id}.

To complete this, please open the following link in the browser you used to start the action!

{website_url}/verify-action?action={vaction_oid}&code={vaction_code}&action_type={vaction_type}

"""


class MailGateway(object):
    def __init__(self, mailgun_url, mailgun_key, mailgun_from, website_url):
        """

        :param mailgun_url:
        :param mailgun_key:
        :param mailgun_from:
        :param website_url:
        """
        self._mailgun_url = mailgun_url
        self._mailgun_key = mailgun_key
        self._mailgun_from = mailgun_from
        self._website_url = website_url

    def send_onboard_verification(self, receiver_email, vaction_oid, vaction_code, expiration_date=''):
        """

        :param receiver_email:
        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        email_body = _ONBOARD_VERIFICATION_EMAIL_BODY.format(website_url=self._website_url,
                                                             vaction_oid=vaction_oid,
                                                             vaction_code=vaction_code,
                                                             vaction_type=VerificationType.MEMBER_ONBOARD_EMAIL,
                                                             expiration_date=expiration_date,
                                                             member_email=receiver_email,
                                                             operator_email='support@crossbario.com')

        email_data = {
            "from": self._mailgun_from,
            "to": [receiver_email],
            "subject": _ONBOARD_VERIFICATION_EMAIL_TITLE,
            "text": email_body
        }

        res = requests.post(url=self._mailgun_url, auth=("api", self._mailgun_key), data=email_data)
        if res.status_code != 200:
            raise RuntimeError('Mailgun gateway HTTP/POST via "{}" failed for sender "{}" with status code {}'.format(
                self._mailgun_url, self._mailgun_from, res.status_code))

    def send_login_verification(self,
                                receiver_email,
                                vaction_oid,
                                vaction_code,
                                wallet_address,
                                expiration_date='',
                                was_signup_request=False):
        """

        :param receiver_email:
        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        if was_signup_request:
            email_body = _SIGNUP_TO_LOGIN_VERIFICATION_EMAIL_BODY.format(
                website_url=self._website_url,
                vaction_oid=vaction_oid,
                vaction_code=vaction_code,
                vaction_type=VerificationType.MEMBER_LOGIN_EMAIL,
                expiration_date=expiration_date,
                member_email=receiver_email,
                operator_email='support@crossbario.com',
                wallet_address=wallet_address)
        else:
            email_body = _LOGIN_VERIFICATION_EMAIL_BODY.format(website_url=self._website_url,
                                                               vaction_oid=vaction_oid,
                                                               vaction_code=vaction_code,
                                                               vaction_type=VerificationType.MEMBER_LOGIN_EMAIL,
                                                               expiration_date=expiration_date,
                                                               member_email=receiver_email,
                                                               operator_email='support@crossbario.com')

        email_data = {
            "from": self._mailgun_from,
            "to": [receiver_email],
            "subject": _LOGIN_VERIFICATION_EMAIL_TITLE,
            "text": email_body
        }

        res = requests.post(url=self._mailgun_url, auth=("api", self._mailgun_key), data=email_data)
        if res.status_code != 200:
            raise RuntimeError('Mailgun gateway HTTP/POST via "{}" failed for sender "{}" with status code {}'.format(
                self._mailgun_url, self._mailgun_from, res.status_code))

    def send_wrong_wallet_email(self, receiver_email, actual_address, address_used):
        email_body = _ACCOUNT_EXISTS_EMAIL_BODY.format(website_url=self._website_url,
                                                       address_used=address_used,
                                                       address_associated=actual_address,
                                                       email=receiver_email)

        email_data = {
            "from": self._mailgun_from,
            "to": [receiver_email],
            "subject": _ACCOUNT_EXISTS_EMAIL_TITLE,
            "text": email_body
        }

        res = requests.post(url=self._mailgun_url, auth=("api", self._mailgun_key), data=email_data)
        if res.status_code != 200:
            raise RuntimeError('Mailgun gateway HTTP/POST via "{}" failed for sender "{}" with status code {}'.format(
                self._mailgun_url, self._mailgun_from, res.status_code))

    def send_create_market_verification(self, receiver_email, vaction_oid, vaction_code, expiration_date=''):
        """

        :param receiver_email:
        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        email_body = _CREATE_MARKET_VERIFICATION_EMAIL_BODY.format(
            website_url=self._website_url,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            vaction_type=VerificationType.MEMBER_CREATEMARKET_EMAIL,
            expiration_date=expiration_date,
            member_email=receiver_email,
            operator_email='support@crossbario.com')

        email_data = {
            "from": self._mailgun_from,
            "to": [receiver_email],
            "subject": _CREATE_MARKET_VERIFICATION_EMAIL_TITLE,
            "text": email_body
        }

        res = requests.post(url=self._mailgun_url, auth=("api", self._mailgun_key), data=email_data)
        if res.status_code != 200:
            raise RuntimeError('Mailgun gateway HTTP/POST via "{}" failed for sender "{}" with status code {}'.format(
                self._mailgun_url, self._mailgun_from, res.status_code))

    def send_join_market_verification(self,
                                      receiver_email,
                                      vaction_oid,
                                      vaction_code,
                                      expiration_date='',
                                      member_id=None,
                                      market_id=None,
                                      roles=None):
        """

        :param receiver_email:
        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        email_body = _JOIN_MARKET_VERIFICATION_EMAIL_BODY.format(website_url=self._website_url,
                                                                 vaction_oid=vaction_oid,
                                                                 vaction_code=vaction_code,
                                                                 vaction_type=VerificationType.MEMBER_JOINMARKET_EMAIL,
                                                                 expiration_date=expiration_date,
                                                                 member_email=receiver_email,
                                                                 member_id=member_id,
                                                                 market_id=market_id,
                                                                 roles=roles,
                                                                 operator_email='support@crossbario.com')

        email_data = {
            "from": self._mailgun_from,
            "to": [receiver_email],
            "subject": _JOIN_MARKET_VERIFICATION_EMAIL_TITLE.format(member_id=member_id,
                                                                    market_id=market_id,
                                                                    roles=roles),
            "text": email_body
        }

        res = requests.post(url=self._mailgun_url, auth=("api", self._mailgun_key), data=email_data)
        if res.status_code != 200:
            raise RuntimeError('Mailgun gateway HTTP/POST via "{}" failed for sender "{}" with status code {}'.format(
                self._mailgun_url, self._mailgun_from, res.status_code))
