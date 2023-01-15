# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from pprint import pformat

from crossbar.shell import client


async def main(session):
    """
    Connect to CFC, get system status and exit.
    """
    status = await session.call(u'crossbarfabriccenter.domain.get_status')
    session.log.info('CFC domain status:\n{status}', status=pformat(status))


if __name__ == '__main__':
    client.run(main)
