RLinks
==========

Nomenclature
    - 1..9, A..F - nodes with RLinks
    - U,V,W,X,Y,Z - nodes without RLinks
    - l - local
    - r - remote
    - lr - local and remote (both)

Node specification **N(\<target\>[l | r | lr])**, where N is the node number, target is the target node number, and **l | r | lr** -  Local/Remote/Both

.. note::

    Local (RLinkLocalSession) have authrole `trusted` and can see all registrations and events from
    other all other sessions including remote (RLinkRemoteSession) sessions.

    Remote (RLinkRemoteSession) have authrole `rlink` and can only see registrations local to the router,
    but not from other rlinks. This is not the case for subscriptions:, remote session can see all events from
    all sessions which results in full mesh subscriptions

Topologies
~~~~~~~~~~

Two routers

- 1[Xl],X - simple node with RLink to X, forwarding local invocations/events to X
- 1[Xr],X - simple node with RLink to X, forwarding forwarding remote invocations/events from X
- 1[Xlr],X - bi-directional RLink to X

Chain

- 1[2l],2[3l],3[Xl],X - chain of nodes with RLinks to the next node, forwarding local invocations/events to the next node
- 1[2r],2[3r],3[Xr],X - chain of nodes with RLinks to the next node, forwarding remote invocations/events from the next node
- 1[2lr],2[3lr],3[Xlr],X - chain of nodes with bi-directional RLinks to the next node

Chain with reciprocal links

- 1[2l],2(1l,3l),3(2l,4l),4(3l) - chain of nodes with RLinks to the next node, forwarding local invocations/events to the next node, and reciprocal links to the previous node
- 1[2r],2(1r,3r),3(2r,4r),4(3r) - chain of nodes with RLinks to the next node, forwarding remote invocations/events from the next node, and reciprocal links to the previous node
- 1[2lr],2(1lr,3lr),3(2lr,4lr),4(3lr) - [INVALID] Oversubscribed chain of nodes with bi-directional RLinks to the next node, and reciprocal links to the previous node

Ring

- 1[2l],2[3l],3[4l],4[1l] - ring of nodes with RLinks to the next node, forwarding local invocations/events to the next node
- 1[2r],2[3r],3[4r],4[1r] - ring of nodes with RLinks to the next node, forwarding remote invocations/events from the next node
- 1[2lr],2[3lr],3[4lr],4[1lr] - ring of nodes with bi-directional RLinks to the next node

Ring with reciprocal links

- 1[2l],2(1l,3l),3(2l,4l),4(3l,1l) - ring of nodes with RLinks to the next node, forwarding local invocations/events to the next node, and reciprocal links to the previous node
- 1[2r],2(1r,3r),3(2r,4r),4(3r,1r) - ring of nodes with RLinks to the next node, forwarding remote invocations/events from the next node, and reciprocal links to the previous node
- 1[2lr],2(1lr,3lr),3(2lr,4lr),4(3lr,1lr) - [INVALID] Oversubscribed ring of nodes with bi-directional RLinks to the next node, and reciprocal links to the previous node

Star

- 1[Xl],2[Xl],3[Xl],4[Xl],X - star (inward) of nodes with RLinks to the central node, forwarding local invocations/events to the central node
- 1[Xr],2[Xr],3[Xr],4[Xr],X - star (inward) of nodes with RLinks to the central node, forwarding remote invocations/events from the central node
- 1[Xlr],2[Xlr],3[Xlr],4[Xlr],X - star (inward) of nodes with bi-directional RLinks to the central node
- 1(Xl, Yl, Zl),X,Y,Z - star (outward) of central node with RLinks to the outward nodes, forwarding local invocations/events to the outward nodes
- 1(Xr, Yr, Zr),X,Y,Z - star (outward) of central node with RLinks to the outward nodes, forwarding remote invocations/events from the outward nodes
- 1(Xlr, Ylr, Zlr),X,Y,Z - star (outward) of central node with bi-directional RLinks to the outward nodes

Star with reciprocal links

- 1[Cl],2[Cl],3[Cl],4[Cl],C(1l,2l,3l,4l) - star of nodes with RLinks to the central node, forwarding local invocations/events to the central node, and reciprocal links from the central node
- 1[Cr],2[Cr],3[Cr],4[Cr],C(1r,2r,3r,4r) - star of nodes with RLinks to the central node, forwarding remote invocations/events from the central node, and reciprocal links from the central node

Mesh

- 1[2l,3l,4l],2[1l,3l,4l],3[1l,2l,4l],4[1l,2l,3l] - mesh of nodes with RLinks to all other nodes and reciprocal links (all forwarding local invocations/events)
- 1[2r,3r,4r],2[1r,3r,4r],3[1r,2r,4r],4[1r,2r,3r] - mesh of nodes with RLinks to all other nodes and reciprocal links (all forwarding remote invocations/events)
- 1[2lr,3lr,4lr],2[1lr,3lr,4lr],3[1lr,2lr,4lr],4[1lr,2lr,3lr] - [OVERKILL/INVALID] mesh of nodes with bi-directional RLinks to all other nodes and reciprocal links

