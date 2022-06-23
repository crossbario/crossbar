from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import SubscribeOptions


class SubscriberBackend(ApplicationSession):

    async def onJoin(self, details):
        self.log.debug("Connected:  {details}", details=details)

        self._cnt_received = 0
        N = 100

        def on_event(evt, counter, value3=None, details=None):
            self._cnt_received += 1
            if self._cnt_received % N == 0:
                self.log.info('{session} received {cnt} events so far ..',
                              session=self._session_id, cnt=self._cnt_received)

        sub = await self.subscribe(on_event, 'com.example.geoservice.',
                                   options=SubscribeOptions(match='prefix', details_arg='details'))

        self.log.info('Subscribed to "com.example.geoservice." with prefix match: {sub}', sub=sub)
