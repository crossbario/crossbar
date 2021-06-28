import os
import random

from autobahn import util
from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import PublishOptions, SubscribeOptions


class PublisherBackend(ApplicationSession):

    async def onJoin(self, details):
        self.log.debug("Connected:  {details}", details=details)

        self._cnt_received = 0
        N = 100

        def on_event(evt, counter, value3=None, details=None):
            self._cnt_received += 1
            if self._cnt_received % N == 0:
                self.log.info('Received {cnt} events so far ..', cnt=self._cnt_received)

        sub = await self.subscribe(on_event, 'com.example.geoservice.',
                                   options=SubscribeOptions(match='prefix', details_arg='details'))

        self.log.debug('Subscribed to "com.example.geoservice." with prefix match: {sub}', sub=sub)

        self._cnt_sent = 0
        N = 100
        publish_options = PublishOptions(acknowledge=False,
                                         exclude_me=False,
                                         exclude=[1, 2, 3],
                                         exclude_authid=['badguy1', 'badguy2'],
                                         exclude_authrole=['hacker', 'fool'],
                                         # eligible=[1, 2, 3],
                                         # eligible_authid=['anonymous'],
                                         eligible_authrole=['anonymous'])

        while True:
            for j in range(10):
                category = random.choice(['alert', 'warning', 'info', 'ad', 'other'])
                x = random.randint(0, 100)
                y = random.randint(0, 100)
                value1 = os.urandom(16)
                value2 = random.random()
                value3 = util.generate_activation_code()

                evt = {
                    'category': category,
                    'x': x,
                    'y': y,
                    'value1': value1,
                    'value2': value2,
                    'value3': value3,
                    'i': self._cnt_sent,
                    'j': j,
                }
                topic = 'com.example.geoservice.{}.{}.{}'.format(category, x, y)

                # self.publish(topic, evt, self._cnt_sent, value3=value3)
                # await self.publish(topic, evt, self._cnt_sent, value3=value3, options=publish_options)
                self.publish(topic, evt, self._cnt_sent, value3=value3, options=publish_options)

                self._cnt_sent += 1
                if self._cnt_sent % N == 0:
                    self.log.info('published {cnt} events ..', cnt=self._cnt_sent)

            await sleep(.1)
