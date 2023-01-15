# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from pprint import pformat

from crossbar.shell import client


async def main(session):
    """
    Connect to (a user management realm on) CFC, get status and exit.

    This is about the most basic example possible. You can copy this
    example and add your CFC calls, reuse the example driver (client.py)
    and get started super quickly.
    """
    status = await session.call(u'crossbarfabriccenter.mrealm.get_status')
    session.log.info('CFC status:\n{status}', status=pformat(status))


if __name__ == '__main__':
    client.run(main)
