import time
import re
import timeit
from pprint import pprint

import zlmdb

from cfxdb import Schema


db = zlmdb.Database('crossbar/.testdb', maxsize=2**30, readonly=True)
schema = Schema.attach(db)


def test1(verbose=False):
    with db.begin() as txn:

        total = schema.events.count(txn)

        for pub in schema.publications.select(txn, limit=1, return_keys=False):

            # print all event attributes
            print('Publication:')
            print('{:>20}: {}'.format('timestamp', pub.timestamp))
            print('{:>20}: {}'.format('publication', pub.publication))
            print('{:>20}: {}'.format('publisher', pub.publisher))
            print('{:>20}: {}'.format('topic', pub.topic))
            print('{:>20}: {}'.format('args', pub.args))
            print('{:>20}: {}'.format('kwargs', pub.kwargs))
            print('{:>20}: {}'.format('payload', pub.payload))
            print('{:>20}: {}'.format('acknowledge', pub.acknowledge))
            print('{:>20}: {}'.format('retain', pub.retain))
            print('{:>20}: {}'.format('exclude_me', pub.exclude_me))
            print('{:>20}: {}'.format('exclude', pub.exclude))
            print('{:>20}: {}'.format('exclude_authid', pub.exclude_authid))
            print('{:>20}: {}'.format('exclude_authrole', pub.exclude_authrole))
            print('{:>20}: {}'.format('eligible', pub.eligible))
            print('{:>20}: {}'.format('eligible_authid', pub.eligible_authid))
            print('{:>20}: {}'.format('eligible_authrole', pub.eligible_authrole))
            print('{:>20}: {}'.format('enc_algo', pub.enc_algo))
            print('{:>20}: {}'.format('enc_key', pub.enc_key))
            print('{:>20}: {}'.format('enc_serializer', pub.enc_serializer))
            print()

            # get publisher session details
            session = schema.sessions[txn, pub.publisher]

            # print all session attributes
            print('Publisher:')
            print('{:>20}: {}'.format('session', session.session))
            print('{:>20}: {}'.format('joined_at', session.joined_at))
            print('{:>20}: {}'.format('left_at', session.left_at))
            print('{:>20}: {}'.format('realm', session.realm))
            print('{:>20}: {}'.format('authid', session.authid))
            print('{:>20}: {}'.format('authrole', session.authrole))
            print()

            # get all events for publication from table (publication, subscription, receiver) -> event
            from_key = (pub.publication, 0, 0)
            to_key = (pub.publication + 1, 0, 0)
            found = schema.events.count_range(txn, from_key=from_key, to_key=to_key)
            if found > 0:
                print('Events: found {} events ({} total)'.format(found, total))
                if verbose:
                    for evt in schema.events.select(txn, from_key=from_key, to_key=to_key, return_keys=False):
                        print('     timestamp={}, receiver={}'.format(evt.timestamp, evt.receiver))
            else:
                print('Events: there were no receivers of this publication!')


def test2(verbose=False):
    pat = re.compile(r'^com\.example\.geoservice\.([a-z]+)\.([0-9]+).([0-9]+)$')

    def trunc(val):
        return int(val / 25)

    started = time.perf_counter()
    total = 0

    res1 = {}
    res2 = {}
    with db.begin() as txn:
        for pub in schema.publications.select(txn, limit=1000000-1, return_keys=False):
            total += 1
            m = pat.match(pub.topic)
            if m:
                category, x, y = m.groups()

                key = (trunc(int(x)), trunc(int(y)))
                if key not in res1:
                    res1[key] = 0
                res1[key] += 1

                if category not in res2:
                    res2[category] = 0
                res2[category] += 1

    ended = time.perf_counter()

    if verbose:
        pprint(res1)
        pprint(res2)

    recs_per_sec = int(float(total) / (ended - started))
    print('{} records in {:.2} secs ({} records per sec)'.format(total, ended - started, recs_per_sec))

    return recs_per_sec


def test3(verbose=False):
    started = time.perf_counter()
    total = 0

    res = {}
    final = {}
    with db.begin() as txn:
        for evt in schema.events.select(txn, limit=1000000-1, return_keys=False):
            total += 1
            if evt.receiver not in res:
                res[evt.receiver] = 0
            res[evt.receiver] += 1

        for receiver in res:
            session = schema.sessions[txn, receiver]
            final[session.authid] = res[receiver]

    ended = time.perf_counter()
    recs_per_sec = int(float(total) / (ended - started))

    if verbose:
        pprint(final)

    print('{} records in {:.2} secs ({} records per sec)'.format(total, ended - started, recs_per_sec))

    return recs_per_sec


print('-' * 80)

test1(True)
print('-' * 80)
#test2()
#test3()

timeit.timeit(test2, number=10)
print('-' * 80)

timeit.timeit(test3, number=10)
print('-' * 80)
