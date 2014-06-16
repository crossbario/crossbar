A new contributor enters username and email.

This must match the author as appearing in patches and commits:

```
commit cd22ca39b1e7399cfc070a4815a1905556ddcb13
Author: Ahmed Kachkach <ahmed.kachkach@gmail.com>
Date:   Mon May 26 00:17:17 2014 -0700
...
```

A unique CLA in PDF format is generated. The unique information includes:

 * CLA serial number
 * issue date and timestamp
 * contributor name
 * contributor email

This PDF is stored persistently. Then an email is generated that contains the PDF as an attachement, plus a unique HTTP link. The contributor is expected to click the link to finally agree to the CLA. This click will be stored together with the PDF.

The PDF together with click information, as well as contributor name and email are added to the repository in an automated way. This allows to correlate code changes in the repository with contributor legally binding CLAs in an unambigious way.
