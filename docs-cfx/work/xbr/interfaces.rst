XBR Interfaces
==============

Write me ...

.. code-block:: yaml

    - foo:int
    - bar:str

.. class:: com.example.weather

    Weather point API.

    This API allows to collect micro weather data from large numbers
    of measuring sites. Each micro weather measuring site runs a
    service that implements this API, and a micro weather consumer
    can access all or a subset of the providers.

    .. version: 2

    .. method:: get_current(period)

        **Procedure** to get the current weather averaged over
        the specified period.

        :param period: The time period from now into the past over
            which to aggregated the weather. Must be ``"day"``
            or ``"hour"``.
        :type period: str
        :returns: The weather (``weather_tick``) aggregated over the
            desired period.
        :rtype: dict

    .. method:: on_weather_tick_5min(weather_tick)

        **Event** with weather tick data aggregated over the last 5 minutes.
        This event fires every 150 seconds. Thus, the aggregation is over a
        sliding window of 5 min, every 2.5 min.


.. class:: xbr.service.payment

    Standard payment interface every XBR service must implement.

    .. attribute:: no_such_key

        **Error** raised when the key referred does not exist.


    .. attribute:: insufficient_amount

        **Error** raised when the amount in a payment is insufficient for the key to be purchased.


    .. method:: buy(seq_id, key_id, amount, balance_remaining, signatures)

        **Procedure** called by a **XBR Market** in delegating a **XBR Consumer**
        to buy a data key.

        The returned data key returned by the **XBR Provider** is encrypted with
        the service private key, and the originally calling **XBR Consumer** public
        key. The returned data key is hence only readable by the **XBR Consumer** (not
        the delegating **XBR Market**).

        :param seq_id: Each payment transaction initiated (by the XBR Market in this
            payment channel with the XBR Provider) is sequentially numbered starting
            from 1.
        :type seq_id: int
        :param key_id: The ID of the key to buy. The original caller, that is the
            XBR Consumer specifies the key_id it wishes to buy
        :type key_id: str
        :param amount: The amount of XBR token paid by the XBR Market to the XBR Provider
            (delegating the XBR Consumer, the ultimate buyer).
        :type amount: int
        :param balance_remaining: The remaining balance in XBR token of the XBR Market
            in the payment channel with the XBR Provider
        :type balance_remaining: int
        :param signature: The signatures of the XBR Consumer and the XBR Market for
            the payment transaction
        :type signature: list
        :returns: The Ed25519 private key for the ``key_id`` in Hex encoding
            (64 characters for the 32 bytes of the key)
        :rtype: str
        :raises: ``no_such_key``
        :raises: ``insufficient_amount``
