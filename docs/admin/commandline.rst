The Command Line
================

Crossbar.io comes as a command line tool ``crossbar`` which works
identical across all supported platforms.

-  `Quick Reference <#quick-reference>`__
-  `Getting Help <#getting-help>`__
-  `Initializing a Node <#initializing-a-node>`__
-  `Starting and Stopping a Node <#starting-and-stopping-a-node>`__

Quick Reference
---------------

Here is a quick reference of all commands available in the Crossbar.io
CLI:


.. code-block:: console

    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ crossbar status --assert=stopped
    Assert status STOPPED succeeded: status is STOPPED
    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ nohup crossbar start &
    [1] 24134
    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ nohup: ignoriere Eingabe und hänge Ausgabe an 'nohup.out' an

    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ <CROSSBAR:REACTOR_RUN>
    <CROSSBAR:REACTOR_STARTING>
    <CROSSBAR:REACTOR_STARTED>
    <CROSSBAR:NODE_STARTING>
    <CROSSBAR:NODE_STARTED>

    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ crossbar status --assert=running
    Assert status RUNNING succeeded: status is RUNNING
    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ crossbar stop
    Stopping Crossbar.io currently running from node directory /tmp/test/.crossbar (PID 24134) ...
    SIGINT sent to process 24134 .. waiting for exit (5 seconds) ...
    <CROSSBAR:NODE_SHUTDOWN_REQUESTED>
    <CROSSBAR:REACTOR_STOPPING>
    <CROSSBAR:NODE_SHUTDOWN_ON_WORKER_EXIT>
    <CROSSBAR:REACTOR_STOPPED>
    <CROSSBAR:EXIT_WITH_SUCCESS>
    Process 24134 has excited gracefully.
    [1]+  Fertig                  nohup crossbar start
    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$ crossbar status --assert=stopped
    Assert status STOPPED succeeded: status is STOPPED
    (cpy365_2) oberstet@thinkpad-t430s:/tmp/test$
