#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from txaio import use_twisted  # noqa
from txaio import make_logger

from autobahn.util import hltype

from crossbar.interfaces import IRealmInventory

__all__ = ('RealmInventory', )


class RealmInventory(IRealmInventory):
    """
    Memory-backed realm inventory.
    """
    INVENTORY_TYPE = 'wamp.eth'

    log = make_logger()

    def __init__(self, personality, factory, config):
        from twisted.internet import reactor

        self._reactor = reactor
        self._personality = personality
        self._factory = factory
        self._config = config

        self._type = self._config.get('type', None)
        assert self._type == self.INVENTORY_TYPE

        self._running = False

        self.log.debug('{func} realm inventory initialized', func=hltype(self.__init__))

    @property
    def type(self) -> str:
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.type`
        """
        return self._type

    @property
    def is_running(self) -> bool:
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.is_running`
        """
        return self._running

    def start(self):
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.start`
        """
        if self._running:
            raise RuntimeError('inventory is already running')
        else:
            self.log.info('{func} starting realm inventory', func=hltype(self.start))

        self._running = True
        self.log.info('{func} realm inventory ready!', func=hltype(self.start))

    def stop(self):
        """
        Implements :meth:`crossbar._interfaces.IRealmInventory.stop`
        """
        if not self._running:
            raise RuntimeError('inventory is not running')
        else:
            self.log.info('{func} stopping realm inventory', func=hltype(self.start))

        self._running = False
