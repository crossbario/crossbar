Introduction
============

XBR extends Crossbar.io Fabric to a platform for running open data markets.

The **five roles in XBR** are:

.. code-block:: console

    ______________
    \             \
     ) Consumers   )
    /_____________/
    ______________
    \             \
     ) Providers   )
    /_____________/
    ______________
    \             \
     ) Markets     )
    /_____________/
    ______________
    \             \
     ) Carriers    )
    /_____________/
    ______________
    \             \
     ) Network     )
    /_____________/

For more information about XBR roles, please see :ref:`xbr-roles`.

----------------


Data and XBR token flow
-----------------------

**Data in XBR flows** from XBR Providers via XBR Carriers to XBR Consumers:

.. code-block:: console

  ______________    ______________    ______________    ______________
  \             \   \             \   \             \   \             \
   ) Provider E  )   ) Carrier D   )   ) Carrier B   )   ) Consumer A  )
  /_____________/   /_____________/   /_____________/   /_____________/

while **XBR tokens flow** from XBR Consumers to XBR Carriers and XBR Markets, and from
XBR Markets to XBR Carriers and XBR Providers:

.. code-block:: console

                        ______________
                        \             \
      ______________     ) Carrier B   )                 ______________
      \             \   /_____________/                  \             \
       ) Consumer A  )  _____________________________     ) Carrier D   )
      /_____________/   \                            \   /_____________/
                         ) Market C                   )  ______________
                        /____________________________/   \             \
                                                          ) Provider E  )
                                                         /_____________/

------------------


Markets and Market Participants
-------------------------------

XBR Consumers and XBR Providers can only exchange data when they have **joined**
the same XBR Market:

.. code-block:: console

    ______________  _____
    \             \ \    \
     ) Consumer A  ) \    \  ______________
    /_____________/   \    \ \             \
    ______________     )    ) ) Market C    )
    \             \   /    / /_____________/
     ) Provider E  ) /    /
    /_____________/ /____/

--------------


Carriers and Subscriptions
--------------------------

XBR Consumers, XBR Providers and XBR Markets rely on XBR Carriers for actual
data transport and routing.

Usually, a Consumer A is subscribed to a Carrier B that is different from
the Carrier D the Provider E is subscribed to.

For Consumer A to use the services of Provider E, the Market C in which both
have joined, must itself be subscribed to Market C:

.. code-block:: console

    ______________  _____
    \             \ \    \
     ) Consumer A  ) \    \  ______________
    /_____________/   \    \ \             \
    ______________     )    ) ) Carrier B   )
    \             \   /    / /_____________/
     ) Market C    ) /    /
    /_____________/ /____/


    ______________  _____
    \             \ \    \
     ) Provider E  ) \    \  ______________
    /_____________/   \    \ \             \
    ______________     )    ) ) Carrier D   )
    \             \   /    / /_____________/
     ) Market C    ) /    /
    /_____________/ /____/


-------------


On-chain transactions
---------------------

The following transactions happen on-chain in XBR:

.. code-block:: console

                                                                  .--------------.
           ______________                                         | Ethereum     |
      o    \             \                                        |              |
     /|\    ) Consumer A  )------------------------------------>  |              |
     / \   /_____________/                                        |              |
           ______________                                         |              |
      o    \             \                                        |              |
     /|\    ) Provider E  )------------------------------------>  |              |
     / \   /_____________/                                        |              |
                             - register with network              |              |
                             - register with carrier              |              |
                             - join market                        |              |
                             - open payment/revenue channel       |              |
                             - close payment/revenue channel      |              |
                             - leave market                       |              |
                             - unregister from carrier            |              |
                             - unregister from network            |              |
                                                                  |              |
                                                                  |              |
          ______________                                          |              |
     o    \             \                                         |              |
    /|\    ) Market C    )------------------------------------->  |              |
    / \   /_____________/                                         |              |
                             - register with network              |              |
                             - register with carrier              |              |
                             - register market                    |              |
                             - open payment channel               |              |
                             - close payment channel              |              |
                             - approve market member              |              |
                             - ban market member                  |              |
                             - unregister market                  |              |
                             - unregister from carrier            |              |
                             - unregister from network            |              |
          ______________                                          |              |
     o    \             \                                         |              |
    /|\    ) Carrier B   )------------------------------------->  |              |
    / \   /_____________/                                         |              |
          ______________                                          |              |
     o    \             \                                         |              |
    /|\    ) Carrier D   )------------------------------------->  |              |
    / \   /_____________/                                         |              |
                             - register with network              |              |
                             - register node                      |              |
                             - unregister node                    |              |
                             - approve subscriber                 |              |
                             - cancel subscriber                  |              |
                             - unregister from network            |              |
                                                                  '--------------'

-------------


Off-chain transactions
----------------------

The following transactions happen on-chain in XBR:

.. code-block:: console
