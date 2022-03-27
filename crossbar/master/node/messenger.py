###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import json
import treq
import os

from txaio import make_logger

from twisted.internet.defer import inlineCallbacks, returnValue

__all__ = ('Messenger', )


class Messenger(object):

    log = make_logger()

    def __init__(self, submit_url, access_key):
        self._submit_url = submit_url
        self._access_key = access_key
        self._mailgun_from = os.environ.get('MAILGUN_FROM', "Crossbar.io <no-reply@mailing.crossbar.io>")

    def send_user_login_mail(self, receiver, activation_code):
        subject = u'Crossbar.io: your LOGIN code'
        text = u'''Hello from Crossbar.io!

        We have received a login request for your account.

        Please use this activation code: {}

        If you did not request a login code, then just ignore this email.
        '''.format(activation_code)
        return self.send_message(receiver, subject, text)

    def send_user_registration_mail(self, receiver, activation_code):
        subject = u'Crossbar.io: your REGISTRATION code'
        text = u'''Hello from Crossbar.io!

        We have received a registration request for this email address.

        Please use this activation code:
            {}
        e.g. to authenticate using the Crossbar.io shell do
            cbsh auth --code {}

        If you did not request a registration, then just ignore this email. No Crossbar.io account will be created for your email address!
        '''.format(activation_code, activation_code)
        return self.send_message(receiver, subject, text)

    @inlineCallbacks
    def send_message(self, receiver, subject, text):

        self.log.info('sending mail via mailgun: receiver={receiver}, subject="{subject}", textlen={textlen}',
                      receiver=receiver,
                      subject=subject,
                      textlen=len(text))

        data = {"from": self._mailgun_from, "to": [receiver], "subject": subject, "text": text}

        res = None
        self.log.debug('Mailgun URL={url}', url=self._submit_url)
        try:
            if self._access_key and self._submit_url:
                res = yield treq.post(self._submit_url, auth=("api", self._access_key), data=data)
            else:
                self.log.warn('Mailgun not configured! This is the mail that would have been sent: {mail}',
                              mail=json.dumps(data))
                res = None
        except Exception as e:
            print('Exception:', e)
            print('Result:', res)
            self.log.failure()
            raise

        returnValue(res)
