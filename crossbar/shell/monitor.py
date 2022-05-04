###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import sys
from pprint import pprint
# import iso8601
import numpy as np

# http://babel.pocoo.org/en/latest/dates.html
# from babel.dates import get_timezone

import txaio

txaio.use_twisted()

from txaio import time_ns, sleep

from twisted.internet.task import react
from twisted.internet.defer import inlineCallbacks

from crossbar.shell.client import create_management_session
from crossbar.master import personality

try:
    import curses
    import curses.panel
    from curses import wrapper
except ImportError:
    print('fatal: curses module not found')
    sys.exit(1)


@inlineCallbacks
def twisted_main(reactor, stdscr=None, mrealms=None, management_url=None, privkey_file=None):
    mrealms = mrealms or ['default']
    try:
        if stdscr:
            stdscr.clear()
            y = 5
            for line in personality.Personality.BANNER.splitlines():
                stdscr.addstr(y, 20, line, curses.color_pair(227))
                y += 1
            y += 3
            stdscr.addstr(y, 24, 'Please wait while collecting data from managed nodes ...')
            stdscr.refresh()

        while True:
            if stdscr:
                stdscr.clear()
                y = 0

                stdscr.addstr(y, 0, '=' * 240)
                y += 1

                x = 0
                stdscr.addstr(y, x, 'Node')
                x += 34
                stdscr.addstr(y, x, 'Mgmt Realm', curses.color_pair(14))
                x += 15
                stdscr.addstr(y, x, 'Node ID', curses.color_pair(14))
                x += 25
                stdscr.addstr(y, x, 'Node OID', curses.color_pair(14))
                x += 40
                stdscr.addstr(y, x, 'Status')
                x += 10
                stdscr.addstr(y, x, 'Last Heartbeat')
                x += 12

                x += 4
                stdscr.addstr(y, x + 0, ' Usr')
                stdscr.addstr(y, x + 5, ' Sys')
                stdscr.addstr(y, x + 10, ' Idl')

                x += 1
                stdscr.addstr(y, x + 15, ' Mem')
                stdscr.addstr(y, x + 20, ' IPv4 sckts')
                x += 5 * 5

                x += 11
                stdscr.addstr(y, x + 0, ' Pxy', curses.color_pair(41))
                stdscr.addstr(y, x + 4, ' Rtr', curses.color_pair(41))
                stdscr.addstr(y, x + 8, ' Xbr', curses.color_pair(41))
                stdscr.addstr(y, x + 12, ' Cnt', curses.color_pair(41))
                stdscr.addstr(y, x + 16, ' Gst', curses.color_pair(41))
                x += 4 * 5

                x += 4
                stdscr.addstr(y, x + 0, ' Rlm', curses.color_pair(227))
                stdscr.addstr(y, x + 5, ' Rls')
                stdscr.addstr(y, x + 10, ' Rlk')
                stdscr.addstr(y, x + 15, '  Sessions', curses.color_pair(41))
                stdscr.addstr(y, x + 25, '  Messages', curses.color_pair(41))
                x += 5 * 5

                y += 1
                stdscr.addstr(y, 0, '-' * 240)
                y += 1

            last_mrealm = None

            for mrealm in mrealms:
                if stdscr:
                    if last_mrealm:
                        stdscr.addstr(y, 0, '.' * 240)
                        y += 1

                try:
                    session, _ = yield create_management_session(url=management_url,
                                                                 realm=mrealm,
                                                                 privkey_file=privkey_file)
                except Exception as e:
                    print(e)

                node_oids = yield session.call('crossbarfabriccenter.mrealm.get_nodes')
                if not stdscr:
                    pprint(node_oids)
                for node_oid in node_oids:
                    node = yield session.call('crossbarfabriccenter.mrealm.get_node', node_oid)
                    if not stdscr:
                        pprint(node)

                    if True:
                        node_authid = node['authid']
                        # node_pubkey = node['pubkey']
                        if node and node['status'] == 'online':

                            node_status = yield session.call('crossbarfabriccenter.remote.node.get_status', node_oid)

                            if not stdscr:
                                pprint(node_status)

                            node_system_stats = yield session.call('crossbarfabriccenter.remote.node.get_system_stats',
                                                                   node_oid)

                            if not stdscr:
                                pprint(node_system_stats)

                            cpu_user = node_system_stats['cpu']['user']
                            cpu_system = node_system_stats['cpu']['system']
                            cpu_idle = node_system_stats['cpu']['idle']
                            # memory_total = node_system_stats['memory']['total']
                            # memory_avail = node_system_stats['memory']['available']
                            memory_perc = node_system_stats['memory']['percent']
                            # network_recv = node_system_stats['network']['bytes_recv_per_sec']
                            # network_sent = node_system_stats['network']['bytes_sent_per_sec']
                            network_conns = node_system_stats['network']['connection']['AF_INET']

                            # tz = get_timezone('Europe/Berlin')
                            # started = format_datetime(iso8601.parse_date(node_status['started']), tzinfo=tz, locale='de_DE', format='long')

                            last_heartbeat = np.datetime64(node['timestamp'], 'ns')
                            now = np.datetime64(time_ns(), 'ns')
                            if now > last_heartbeat:
                                last_heartbeat_ago = str((now - last_heartbeat).astype("timedelta64[s]"))
                            else:
                                last_heartbeat_ago = None
                            node_title = node_status['title']

                            # get IDs for all workers running in this node
                            worker_info = {}
                            router_info = {}
                            workers = yield session.call('crossbarfabriccenter.remote.node.get_workers', node_oid)
                            for worker_id in workers:
                                # get worker detail information
                                # {'id': 'xbr1', 'pid': 11507, 'type': 'marketplace', 'status': 'started', 'created': '2020-06-22T06:15:44.589Z', 'started': '2020-06-22T06:15:48.224Z', 'startup_time': 3.635574, 'uptime': 13949.814363}
                                worker = yield session.call('crossbarfabriccenter.remote.node.get_worker', node_oid,
                                                            worker_id)
                                if not stdscr:
                                    pprint(worker)

                                if worker['status'] == 'started':
                                    if worker['type'] not in worker_info:
                                        worker_info[worker['type']] = 0
                                    worker_info[worker['type']] += 1

                                    if worker['type'] == 'router':
                                        # get IDs for all realm running in router worker
                                        realm_oids = yield session.call(
                                            'crossbarfabriccenter.remote.router.get_router_realms', node_oid,
                                            worker_id)
                                        for realm_oid in realm_oids:
                                            # get realm detail information
                                            realm = yield session.call(
                                                'crossbarfabriccenter.remote.router.get_router_realm', node_oid,
                                                worker_id, realm_oid)

                                            if not stdscr:
                                                pprint(realm)

                                            # get per-realm messaging statistics
                                            realm_stats = yield session.call(
                                                'crossbarfabriccenter.remote.router.get_router_realm_stats', node_oid,
                                                worker_id, realm_oid)

                                            if not stdscr:
                                                pprint(realm_stats)

                                            realm_id = realm['id']
                                            realm_name = realm['config']['name']
                                            realm_created = realm['created']

                                            ri_obj = {
                                                'node_oid': node_oid,
                                                'worker_id': worker_id,
                                                'id': realm_id,
                                                'name': realm_name,
                                                'created': realm_created,
                                                'rlinks': len([1 for rlink in realm['rlinks'] if rlink['connected']]),
                                            }

                                            sw_latest = '20.6.2.dev2' in node_status['title']
                                            if sw_latest:
                                                # get IDs of all rlinks running in this router worker and realm
                                                rlink_oids = yield session.call(
                                                    'crossbarfabriccenter.remote.router.get_router_realm_links',
                                                    node_oid, worker_id, realm_oid)
                                                ri_obj['rlinks'] = len(rlink_oids)

                                            # {'realm001': {'messages': {'received': {'publish': 39, 'register': 42},
                                            #                            'sent': {'registered': 42}},
                                            #               'roles': 4,
                                            #               'sessions': 2}}
                                            received = realm_stats[realm_id]['messages']['received']
                                            sent = realm_stats[realm_id]['messages']['sent']
                                            total = 0
                                            for k in received:
                                                total += received[k]
                                            for k in sent:
                                                total += sent[k]

                                            ri_obj['messages'] = total
                                            ri_obj['received'] = realm_stats[realm_id]['messages']['received']
                                            ri_obj['sent'] = realm_stats[realm_id]['messages']['sent']

                                            ri_obj['sessions'] = realm_stats[realm_id]['sessions']
                                            ri_obj['roles'] = realm_stats[realm_id]['roles']

                                            if realm_name not in router_info:
                                                router_info[realm_name] = [ri_obj]
                                            else:
                                                router_info[realm_name].append(ri_obj)

                        else:
                            worker_info = {}
                            router_info = {}
                            # started = '-'
                            last_heartbeat_ago = '-'
                            node_title = '-'
                            cpu_user = 0
                            cpu_system = 0
                            cpu_idle = 0
                            # memory_total = 0
                            # memory_avail = 0
                            memory_perc = 0
                            # network_recv = 0
                            # network_sent = 0
                            network_conns = 0

                        if stdscr:

                            def fmt(data, key):
                                val = data.get(key, 0)
                                if val:
                                    return '{0: >4}'.format(val), curses.color_pair(41)
                                else:
                                    return '   -', curses.color_pair(8)

                            x = 0

                            stdscr.addstr(y, x, node_title)
                            x += 34

                            stdscr.addstr(y, x, mrealm, curses.color_pair(14))
                            x += 15

                            stdscr.addstr(y, x, node_authid, curses.color_pair(14))
                            x += 25

                            stdscr.addstr(y, x, node_oid, curses.color_pair(14))
                            x += 40

                            if node['status'] == 'online':
                                stdscr.addstr(y, x, node['status'], curses.color_pair(41))
                            else:
                                stdscr.addstr(y, x, node['status'], curses.color_pair(10))
                            x += 10

                            stdscr.addstr(y, x, last_heartbeat_ago)
                            x += 12

                            def fmt2(val):
                                return '{0: >4}'.format(val), curses.color_pair(8)

                            x += 4
                            stdscr.addstr(y, x + 0, *fmt2(round(cpu_user, 1)))
                            stdscr.addstr(y, x + 5, *fmt2(round(cpu_system, 1)))
                            stdscr.addstr(y, x + 10, *fmt2(round(cpu_idle, 1)))

                            x += 1
                            stdscr.addstr(y, x + 15, *fmt2(round(memory_perc, 1)))

                            x += 1
                            stdscr.addstr(y, x + 20, '{0: >10}'.format(network_conns))

                            x += 5 * 5

                            x += 10
                            stdscr.addstr(y, x + 0, *fmt(worker_info, 'proxy'))
                            stdscr.addstr(y, x + 4, *fmt(worker_info, 'router'))
                            stdscr.addstr(y, x + 8, *fmt(worker_info, 'marketplace'))
                            stdscr.addstr(y, x + 12, *fmt(worker_info, 'container'))
                            stdscr.addstr(y, x + 16, *fmt(worker_info, 'guest'))
                            x += 4 * 5

                        # cpu_user = node_system_stats['cpu']['user']
                        # cpu_system = node_system_stats['cpu']['system']
                        # cpu_idle = node_system_stats['cpu']['idle']
                        # memory_total = node_system_stats['memory']['total']
                        # memory_avail = node_system_stats['memory']['available']
                        # memory_perc = node_system_stats['memory']['percent']
                        # network_recv = node_system_stats['network']['bytes_recv_per_sec']
                        # network_sent = node_system_stats['network']['bytes_sent_per_sec']
                        # network_conns = node_system_stats['network']['connection']['AF_INET']

                        roles = 0
                        sessions = 0
                        messages = 0
                        rlinks = 0
                        for realm_id in router_info:
                            for realm_obj in router_info[realm_id]:
                                roles += realm_obj['roles']
                                sessions += realm_obj['sessions']
                                messages += realm_obj['messages']
                                rlinks += realm_obj['rlinks']

                        if stdscr:
                            x += 4
                            stdscr.addstr(y, x + 0, '{0: >4}'.format(len(router_info.keys())), curses.color_pair(227))
                            stdscr.addstr(y, x + 5, '{0: >4}'.format(roles))
                            stdscr.addstr(y, x + 10, '{0: >4}'.format(rlinks))
                            stdscr.addstr(y, x + 15, '{0: >10}'.format(sessions), curses.color_pair(41))
                            stdscr.addstr(y, x + 25, '{0: >10}'.format(messages), curses.color_pair(41))
                            x += 5 * 5

                            y += 1

                last_mrealm = mrealm

            if stdscr:
                stdscr.addstr(y, 0, '=' * 240)
                y += 1

                stdscr.refresh()

            yield sleep(5)
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)


def main(stdscr=None, mrealms=None, management_url=None, privkey_file=None):
    if stdscr:
        # https://stackoverflow.com/a/22166613/884770
        curses.start_color()
        curses.use_default_colors()
        curses.curs_set(0)
        for i in range(0, curses.COLORS):
            curses.init_pair(i + 1, i, -1)

    react(twisted_main, [stdscr, mrealms or ['default'], management_url, privkey_file])


def run(management_url=None, privkey_file=None):
    try:
        wrapper(main, management_url=management_url, privkey_file=privkey_file)
        # main(management_url=management_url, privkey_file=privkey_file)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    run()
