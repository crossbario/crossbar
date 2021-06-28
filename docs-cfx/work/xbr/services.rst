XBR Services
============

**XBR Services** are at the heart of XBR. They are software components run by a XBR Provider that expose data services via WAMP interfaces or APIs ("Application Programming Interfaces").
The "application" in this case is the XBR Consumer side software component that accesses the data service exposed via the WAMP interfaces of the service.

An XBR Service **must implement at least two interfaces**:

* the actual data service interface, e.g. registered at ``com.example.myapp.*``
* a standardized XBR service payment interface, registered at ``xbr.service.<service-id>.payment.*``

While the former can be chosen freely by the XBR Provider of the data service, the latter is defined by the XBR Network, and must always be implemented "as is".


XBR Service Payment Interface
-----------------------------

The Standard XBR Service interface **must be implemented by all XBR Services** as it the interface by which e.g. XBR Consumers can get a price quote from a XBR Service, or by which XBR Markets can buy data keys from XBR Providers as a delegate for XBR Consumers that want to unlock (encrypted) data received.

The Standard XBR Service interface must be registered by a XBR compliant XBR Service under the URI base:

* ``xbr.service.<service_id>.payment.``

The API has

* URI **prefix** ``xbr.service.payment.`` and
* URI **suffix** ``@<version>$<service_id>``

where the ``version`` specifies the API version (numbered from 1), and the ``service_id`` is the ID of the XBR Service implementing this API.

The XBR Service Payment API defines the following WAMP procedures, events and errors for payments:

.. py:function:: quote(key_id)

    Called by **XBR Consumers** to get a price quote for buying some specific key.

    :param PREFIX: ``xbr.service.payment.``, the static URI prefix of the procedure.
    :param SUFFIX: ``@<version>$<service_id>``, where the ``version`` specifies the
        API version (numbered from 1), and the ``service_id`` is the ID of the
        XBR Service implementing this API.
    :param KEY: The call must be encrypted to the public key of the service (for the
        ``service_id``), and using the private key of the XBR Consumer.
    :param RKEY: The call result is encrypted to this public XBR data key, for which
        the XBR Consumer needs to buy the private key.
    :param key_id: The ID of the key to quote a price for.
    :type key_id: str
    :returns: The price quote in XBR token. Note that all amounts and balances in
        XBR tokens are always in 256 bit integers with 19 decimal digits for
        fractional XBR amounts.
    :rtype: int
    :raises: ``xbr.service.payment.error.no-such-key``

.. py:function:: buy(seq_id, key_id, amount, balance_remaining, signatures)

    Called by a **XBR Market** in delegating a ***XBR Consumer** to buy a data key.

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
    :raises: ``xbr.service.payment.error.no-such-key``
    :raises: ``xbr.service.payment.error.no-price-match``

.. py:function:: close(last_seq_id, last_balance_remaining, signatures)

    Can be called by a XBR Market any time to initiate closing of the payment channel
    with the XBR Provider.

    The XBR Market will announce the ``seq_id`` and ``balance_remaining`` it wants to use
    to settle the payment channel.

    When the XBR Provider agrees (is not aware of a transaction with a higher `seq_id`
    and the associated revenue), it should return immediately with success.

    When the XBR Provider disagrees, then the XBR Provider should raise an error.

    Any party (XBR Market or XBR Provider) can initiate the closing of the payment
    channel at any time - but will bare the blockchain gas costs doing so.

    Initiating a channel close will trigger a timer that ensure the channel is indeed
    close even when the other party remains uncooperative (not providing its latest
    transaction and signing off the final agreed payment channel state).

    :param last_seq_id: The ``seq_id`` of last transaction the XBR Market has logged
        and wants to base the closing of the payment channel on.
    :type last_seq_id: int
    :returns: The price quote in XBR token. Note that all amounts and balances in
        XBR tokens are always in 256 bit integers with 19 decimal digits for
        fractional XBR amounts.
    :rtype: int
    :raises: ``xbr.service.payment.error.no-such-key``
