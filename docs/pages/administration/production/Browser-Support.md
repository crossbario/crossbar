title: Browser Support
toc: [Documentation, Administration, Going to Production, Browser Support]

# Browser Support

**The final RFC spec**

WebSocket, as an [IETF standard](http://tools.ietf.org/html/rfc6455), and with a W3C browser API, is fully supported by all modern browsers:

* Chrome 16 + (incl. Chrome for Android)
* Firefox 11 + (incl. Firefox for Android)
* Internet Explorer 10+ (incl. Internet Explorer Mobile on Windows Phone 8)
* Safari 6 +
* Opera 12.1 + (incl. Opera Mobile)
* iOS 6.0 +
* Blackberry 7 +

Generally speaking, on the desktop outside of crazy legacy systems you should be OK. On mobile, older Android versions are the largest (but rapidly shrinking) gap.


**Adding WebSocket support**

***Internet Explorer***

For IE < 10, you can use Adobe Flash Bridge to bring WebSocket Supporting.

IE10+ has native WebSocket support. It is the default browser on Windows 8, and has been rolled out as an update for Windows 7. It is also the browser for Windows Phone 8.


***Android***

We recommend:

* Chrome for Android on Android ICS+.
* Firefox Mobile or Opera Mobile on sub-ICS devices,
* Opera Mobile on ARMv6 devices

The above browsers all offer native WebSocket support. When none of the above is an option, Flash Bridge may be.

Flash is increasing rare on Android devices. It is not supported anymore from 4.1 (Jelly Bean) onward. Other devices, e.g. ARMv6 devices (like the Samsung Galaxy ACE) mostly never had Flash support.

If Flash fallback is needed, obviously, the Flash Plugin must be installed and active.
The setting for Plugins on the Android built-in browser can be changed under "Options->Settings->Active Plugins" and should be left at the default "Always On".

Firefox Mobile runs on ARMv7+ devices, with only experimental support for ARMv6.

Opera Mobile works, and is currently the only option on devices that do not have Flash (ARMv6 e.g. Samsung Galaxy ACE) or that do not have the option to run Chrome Mobile or Firefox.

Opera Mini is NOT supported, since it has only very limited support for JavaScript.

The Android WebView supports WebSocket only starting at Android 4.4, since at this point it was switched to the Chromium engine from the Android browser.


***Opera***

Opera 12.1+ (both desktop and mobile) has full WebSocket support, and of course the newer Operas, which are based on Google's Blink engine, share its WebSocket support.

***Safari***

* Safari 6.0+ has full WebSocket support.


***Supporting Flash bridge***

When using browsers without any native WebSocket support, such support can be added via a flash shim such as [web-socket-js](https://github.com/gimite/web-socket-js/).

In order for this to work, 'Flash Policy Server' in Crossbar.io needs to be active. This requires a restart to take effect.

Additionally, the 'Flash Policy Port' should be set correctly to '843'.
