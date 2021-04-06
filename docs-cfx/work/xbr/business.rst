Business Considerations
=======================

This chapter discusses a number of key questions and considerations for XBR stakeholders, where business interests touch technical aspects, such as APIs, quality of data or service and pricing.

-------------


XBR Roles and Key Benefits
--------------------------

The key benefits of XBR vary depending on the role of the stakeholder or user of XBR:

1. **XBR Consumers**: can access and integrate high quality and competitively priced real-time data services into their apps and systems
2. **XBR Providers**: can monetize their data services to an open network of consumers and cash in the major chunk of fees from consumers
3. **XBR Markets**: can monetize their ability to set market rules, match data consumers and providers and operate reliable real-time balances and transactions
4. **XBR Carriers**: can monetize their ability to operate critical data routing and carriage infrastructure

-------------


XBR Roles and Business Models
-----------------------------

XBR is designed to benefit all stakeholders in the *XBR Network*, in all sections of digital value chains:

**(XBR Consumer A)** << **(XBR Carrier B)** << **(XBR Market C)** << **(XBR Carrier D)** << **(XBR Provider E)**

Here, data flows **<<**, from providers to consumers, and XBR tokens flow **>>** as a means of payment for the consumed data. There can be many different A, B, C, D and E participants in the **XBR Network**, held together for *global clearing (only)* via a shared consensus public blockchain (Ethereum) and token (XBR).

Different integrated business models are conceivable based on above most granular decomposition of digital value chains:

* **[A] << [B] << [C] << [D] << [E]**: fully disintegrated digital value chain
* **[A] << [B] << [C] << [D  <<  E]**: integrated provider-(half)carrier
* **[A] << [B] << [C  <<  D  <<  E]**: integrated consumer-market-(half)carrier
* **[A] << [B  <<  C  <<  D  <<  E]**: integrated consumer-market-carrier
* **[A] << [B  <<  C  <<  D] << [E]**: integrated market-carrier
* ...

.. note::

    For the basic goal of the XBR project, an XBR Markets is always hosted and operated by one XBR Carrier.
    That is, the digital value chain looks like:

    **(XBR Consumer A)** << **(integrated XBR Carrier + XBR Market B)** << **(XBR Provider C)**

    Under this additional constraint, the following integrated business models are still possible:

    * **[A] << [B  <<  C  <<  D] << [E]**: integrated market-carrier
    * **[A] << [B  <<  C  <<  D  <<  E]**: integrated provider-market-carrier
    * **[A  <<  B  <<  C  <<  D] << [E]**: integrated consumer-market-carrier

    The project moonshot goal lifts that limitations and aims for a complete decoupling of XBR Markets and XBR Carriers. See above for how completely disintegrated digital value chains look like in the moonshot goal of XBR.

-------------


Key questions to ask
--------------------

**For XBR Consumers**

1. Is the business value to be gained from accessing **any** single XBR Provider (that might have the best quality or price) or **one** single XBR Provider (that might have a unique API and/or Code and/or Data)?
2. Is the business value to be gained proportional to **number** of XBR Providers accessed or the extent of usage of such XBR providers, over a common API?
3. Are there **other** data services that allow to derive the same business value at a lower cost or higher quality?

--------------

**For XBR Providers**

1. Is the **API** of my data service differentiating for the business value I offer?
2. Is the **Code** of my data service differentiating for the business value I offer?
3. Is the **Data** of my data service differentiating for the business value I offer?

The answers will give you a solid foundation to decide about your *XBR data service product and pricing strategy*.

--------------

**For XBR Markets**

1. Is XBR Market hosting ("white label", e.g. as an addon option to a XBR Carrier offering, possibly private or closed club markets), with service quality and price as differentiators the business value I offer?
2. Is the XBR Market to build up an own brand, with a marketing budget, with differentiating match-making or data service discoverability, so the business value in the specific market is differentiating?
3. Is the XBR Market primarily to offer the data services of a single XBR Provider, and hence there is no "differentiating business value", because the services are only available in this single, exclusive XBR Market?

The answers will give you a solid foundation to decide about your *XBR data market product and pricing strategy*.

--------------

**For XBR Carriers**

1. Is XBR data routing "as-a-service" (for XBR Consumers and Providers), with service quality and price as differentiators the business value I offer?
2. Is an addon option to host XBR Markets a business value I offer?
3. Is an addon option to host XBR Provider data services (in the cloud) a business value I offer?

The answers will give you a solid foundation to decide about your *XBR data carriage product and pricing strategy*.

--------------


More considerations
-------------------

**For Consumers**

Write me.

--------------


**For XBR Providers**

APIs are the way *XBR Providers* offer their data services to *XBR Consumers*. They define the technical viewport through which *XBR Services* are accessed.

One important question from a *XBR Provider* point of view regarding APIs is, if the API itself is supposed to be differentiating, probably protected, and hence the *XBR Provider* being the only party that offers services that implement that API, and whether there is an additional differentiating dataset under the hood is an orthogonal question.
We call that scenario **differentiating API** based data services.

If the API itself is considered non-differentiating, possibly openly developed, shared and available, then the *XBR Provider* will be one of potentially many parties that offers services that implement that API, but will offer said API over an unique dataset only the provider has.
We call that scenario **differentiating Data** based data services.

If neither the API nor the data is considered non-differentiating, the only piece left that can differentiate data services is code that accessed the non-differentiating data and exposes it via a non-differentiating API. That code could be a "magic sauce", some super clever, proprietary AI learning algorithm for example.
We call that scenario **differentiating Code** based data services.

Of course data services may be **differentiating in more than one aspect of API, Data or Code**, but data providers should think and decide about early on, and follow a clear strategy.

--------------


**For XBR Markets**

Write me.

--------------


**For XBR Carriers**

Write me.
