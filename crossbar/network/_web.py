# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import sys
import uuid
import mimetypes
import argparse
import binascii

from twisted.python import log
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource

from flask import Flask, request, session, render_template, redirect

import numpy as np
from txaio import time_ns
from autobahn.util import generate_activation_code

from cfxdb.xbrnetwork import Account, VerifiedAction

from validate_email import validate_email

from ._backend import is_valid_username
from ._mailgw import MailGateway

# make sure we have MIME types defined for all the
# file types we use
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('text/javascript', '.jgz')

# Jinja2 extension for Pygments
#
# Note: To generate Pygments CSS file for style: pygmentize -S default -f html > pygments.css
import jinja2_highlight  # noqa


class SiteFlask(Flask):
    jinja_options = dict(Flask.jinja_options)
    jinja_options.setdefault('extensions', []).append('jinja2_highlight.HighlightExtension')


HAS_HIGHLIGHT = True

# FIXME
_USERNAME_PAT_STR = None

# Main app object
#
app = SiteFlask(__name__)
app.secret_key = str(uuid.uuid4())

app.config['DEBUG'] = True
app.config['WEBSITE_URL'] = 'http://localhost:8090'
# app.config['WEBSITE_URL'] = 'https://xbr.network'
app.config['MAILGUN'] = MailGateway(os.environ.get('MAILGUN_URL', None), os.environ.get('MAILGUN_KEY', None),
                                    os.environ.get('MAILGUN_FROM', 'XBR Network <no-reply@mailing.xbr.network>'),
                                    app.config['WEBSITE_URL'])


@app.route('/')
def page_home():
    session['site_area'] = 'landing'
    session['site-page'] = None
    return render_template('index.html')


@app.route('/privacy/')
def page_privacy():
    session['site_area'] = 'legal'
    session['site-page'] = None
    return render_template('privacy.html')


@app.route('/impressum/')
def page_impressum():
    session['site_area'] = 'legal'
    session['site-page'] = None
    return render_template('anbieterkennung.html')


@app.route('/industrial/')
def page_industrial():
    session['site_area'] = 'sectors'
    session['site-page'] = None
    return render_template('sector_industrial.html')


@app.route('/automotive/')
def page_automotive():
    session['site_area'] = 'sectors'
    session['site-page'] = None
    return render_template('sector_automotive.html')


@app.route('/onboard/')
def page_xbr_onboard():
    session['site_area'] = 'landing'
    session['site-page'] = None
    return render_template('xbr_onboard.html')


@app.route('/submit-onboard', methods=['POST'])
def page_xbr_submit_onboard():
    session['site_area'] = 'landing'
    session['site-page'] = None
    # ImmutableMultiDict([
    #   ('onboard_member_name', 'oberstet'),
    #   ('onboard_member_email', 'tobias.oberstein@crossbario.com'),
    #   ('onboard_wallet_type', 'imported'),
    #   ('onboard_wallet_address', '0x6231eECbA6e7983efe5ce6d16972E16cCcD97CE7'),
    #   ('onboard_accept_eula', 'on')
    # ])
    onboard_member_name = request.form.get('onboard_member_name', None)
    onboard_member_email = request.form.get('onboard_member_email', None)
    onboard_wallet_type = request.form.get('onboard_wallet_type', None)
    onboard_wallet_address = request.form.get('onboard_wallet_address', None)
    onboard_accept_eula = request.form.get('onboard_accept_eula', None)

    print('page_xbr_submit_onboard:')
    print('  onboard_member_name', onboard_member_name)
    print('  onboard_member_email', onboard_member_email)
    print('  onboard_wallet_type', onboard_wallet_type)
    print('  onboard_wallet_address', onboard_wallet_address)
    print('  onboard_accept_eula', onboard_accept_eula)

    if onboard_wallet_type not in Account.WALLET_TYPE_FROM_STRING:
        return render_template('xbr_onboard_submit_error.html',
                               onboard_member_error='Invalid wallet type "{}"'.format(onboard_wallet_type))
    else:
        onboard_wallet_type = Account.WALLET_TYPE_FROM_STRING[onboard_wallet_type]

    if onboard_accept_eula != 'on':
        return render_template('xbr_onboard_submit_error.html', onboard_member_error='EULA must be accepted')

    # eg, onboard_wallet_address = 0x6231eECbA6e7983efe5ce6d16972E16cCcD97CE7
    if len(onboard_wallet_address) != 42:
        return render_template('xbr_onboard_submit_error.html',
                               onboard_member_error='Invalid wallet address "{}"'.format(onboard_wallet_address))

    try:
        onboard_wallet_address = binascii.a2b_hex(onboard_wallet_address[2:])
    except:
        return render_template('xbr_onboard_submit_error.html',
                               onboard_member_error='Invalid wallet address "{}"'.format(onboard_wallet_address))

    if not validate_email(onboard_member_email, check_mx=False, verify=False):
        return render_template('xbr_onboard_submit_error.html',
                               onboard_member_error='Invalid email address "{}"'.format(onboard_member_email))

    if not is_valid_username(onboard_member_name):
        return render_template(
            'xbr_onboard_submit_error.html',
            onboard_member_error='Invalid username "{}" - must be a string matching the regular expression {}'.format(
                onboard_member_name, _USERNAME_PAT_STR))

    db = app.config['DB']
    schema = app.config['DBSCHEMA']

    with db.begin() as txn:
        account_oid = schema.idx_accounts_by_username[txn, onboard_member_name]
        if account_oid:
            return render_template('xbr_onboard_submit_error.html',
                                   onboard_member_error='Username "{}" already exists'.format(onboard_member_name))

    vaction_oid = uuid.uuid4()
    vaction_code = generate_activation_code()
    mailgw = app.config['MAILGUN']
    try:
        mailgw.send_onboard_verification(onboard_member_email, vaction_oid, vaction_code)
    except Exception as e:
        return render_template('xbr_onboard_submit_error.html',
                               onboard_member_error='Failed to submit email via mailgun (exception {})'.format(e))

    on_success_url = '{}/member'.format(app.config['WEBSITE_URL'])
    on_error_url = None
    verified_data = {
        'onboard_member_name': onboard_member_name,
        'onboard_member_email': onboard_member_email,
        'onboard_wallet_type': onboard_wallet_type,
        'onboard_wallet_address': onboard_wallet_address,
        'on_success_url': on_success_url,
        'on_error_url': on_error_url,
    }

    with db.begin(write=True) as txn:
        # double check (again) for username collision, as the mailgun email submit happens async in above after
        # we initially checked for collision
        account_oid = schema.idx_accounts_by_username[txn, onboard_member_name]
        if account_oid:
            return render_template('xbr_onboard_submit_error.html',
                                   onboard_member_error='Username "{}" already exists'.format(onboard_member_name))

        vaction = VerifiedAction()
        vaction.oid = vaction_oid
        vaction.created = np.datetime64(time_ns(), 'ns')
        vaction.vtype = VerifiedAction.VERIFICATION_TYPE_ONBOARD_MEMBER
        vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
        vaction.vcode = vaction_code
        # vaction.verified_oid = None
        vaction.verified_data = verified_data

        schema.verified_actions[txn, vaction.oid] = vaction

    return render_template('xbr_onboard_submit_success.html',
                           onboard_member_email=onboard_member_email,
                           vaction_oid=vaction_oid)


# https://xbr.network/verify-action?code=82a996c7815e528a26bb21e81216c56df38a3eb06109134569ddc5cbdc77454a
@app.route('/verify-action/')
def page_xbr_verify_action():
    session['site_area'] = 'landing'
    session['site-page'] = None
    vaction_oid = request.args.get('action', None)
    vaction_code = request.args.get('code', None)
    member_onboarded = app.config['NETWORK'].verify_onboard_member(vaction_oid, vaction_code)
    print('member onboarded:', member_onboarded)
    return redirect('/member/')


@app.route('/member/<path:member_adr>')
def page_xbr_member(member_adr=None):
    session['site_area'] = 'landing'
    session['site-page'] = None
    member_adr = request.args.get('member_adr', None)
    return render_template('xbr_member.html', member_adr=member_adr)


@app.route('/market/<path:market_id>')
def page_xbr_market(market_id):
    session['site_area'] = 'landing'
    session['site-page'] = None
    return render_template('xbr_market.html', market_id=market_id)


@app.route('/market')
def page_xbr_market_query():
    market_id = request.args.get('market_id', '0x00000000000000000000000000000000')
    return page_xbr_market(market_id)


@app.route('/channel/<path:channel_adr>')
def page_xbr_channel(channel_adr):
    session['site_area'] = 'landing'
    session['site-page'] = None
    return render_template('xbr_channel.html', channel_adr=channel_adr)


@app.route('/channel')
def page_xbr_channel_query():
    channel_adr = request.args.get('channel_adr', '0x00000000000000000000000000000000')
    return page_xbr_channel(channel_adr)


@app.route('/address/<path:address>')
def page_xbr_address(address):
    session['site_area'] = 'landing'
    session['site-page'] = None
    return render_template('xbr_address.html', address=address)


@app.route('/address')
def page_xbr_address_query():
    address = request.args.get('address', '0x00000000000000000000000000000000')
    return page_xbr_address(address)


@app.route('/console')
def page_xbr_console():
    return render_template('xbr_console.html')


@app.route('/editor')
def page_editor():
    session['site_area'] = 'landing'
    session['site-page'] = None
    return render_template('test_editor.html')


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output.")
    parser.add_argument("-n",
                        "--nonetwork",
                        action="store_true",
                        help="No public internet/networking, disable external code (Google Analytics, Disqus).")
    parser.add_argument("-f", "--freeze", action="store_true", help="Enable freeze mode.")
    parser.add_argument("--port",
                        type=int,
                        default=8080,
                        help='Web port to use for embedded Web server. Use 0 to disable.')
    parser.add_argument("--mailgun_key",
                        type=str,
                        default=None,
                        help='Mailgun key (eg "key-00000000000000000000000000000000")')
    parser.add_argument("--mailgun_url",
                        type=str,
                        default=None,
                        help='Mailgun posting URL (eg "https://api.mailgun.net/v3/mailing.crossbar.io/messages")')
    options = parser.parse_args()

    if options.mailgun_key:
        app.config['MAILGUN_KEY'] = options.mailgun_key

    if options.mailgun_url:
        app.config['MAILGUN_URL'] = options.mailgun_url

    app.config['DEBUG'] = options.debug
    app.config['NONETWORK'] = options.nonetwork

    if options.freeze:
        # freeze mode
        from flask_frozen import Freezer
        freezer = Freezer(app)

        freezer.freeze()
    else:
        # dynamic serving mode
        log.startLogging(sys.stdout)
        resource = WSGIResource(reactor, reactor.getThreadPool(), app)
        site = Site(resource)
        site.noisy = False
        site.log = lambda _: None
        reactor.listenTCP(options.port, site)
        reactor.run()
