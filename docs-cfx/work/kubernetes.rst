
sudo snap install kubectl --classic

curl -Lo minikube https://storage.googleapis.com/minikube/releases/v0.30.0/minikube-linux-amd64 && chmod +x minikube && sudo cp minikube /usr/local/bin/ && rm minikube

sudo apt install libvirt-clients libvirt-daemon-system qemu-kvm
sudo usermod -a -G libvirt $(whoami)
newgrp libvirt




--vm-driver=none

https://github.com/kubernetes/ingress-nginx#what-is-an-ingress-controller


.. code-block:: note

    What is an Ingress Controller?

    Configuring a webserver or loadbalancer is harder than it should be. Most webserver configuration
    files are very similar. There are some applications that have weird little quirks that tend to
    throw a wrench in things, but for the most part you can apply the same logic to them and
    achieve a desired result.

    The Ingress resource embodies this idea, and an Ingress controller is meant to handle all the
    quirks associated with a specific "class" of Ingress.

    An Ingress Controller is a daemon, deployed as a Kubernetes Pod, that watches the
    apiserver's /ingresses endpoint for updates to the Ingress resource. Its job is to
    satisfy requests for Ingresses.

https://kubernetes.github.io/ingress-nginx/
https://kubernetes.github.io/ingress-nginx/deploy/
https://kubernetes.github.io/ingress-nginx/deploy/#aws
https://kubernetes.github.io/ingress-nginx/deploy/upgrade/


https://kubernetes.io/docs/concepts/services-networking/service/
https://kubernetes.io/docs/concepts/services-networking/service/#ips-and-vips
https://kubernetes.io/docs/concepts/services-networking/service/#iptables
https://kubernetes.io/docs/concepts/services-networking/ingress/

https://github.com/helm/charts/tree/master/stable/nginx-ingress

https://github.com/kubernetes/ingress-nginx
https://github.com/nginxinc/kubernetes-ingress


.. code-block:: yaml

    kind: Service
    apiVersion: v1
    metadata:
    name: ingress-nginx
    namespace: ingress-nginx
    labels:
        app.kubernetes.io/name: ingress-nginx
        app.kubernetes.io/part-of: ingress-nginx
    annotations:
        # by default the type is elb (classic load balancer).
        service.beta.kubernetes.io/aws-load-balancer-type: nlb
    spec:
    # this setting is to make sure the source IP address is preserved.
    externalTrafficPolicy: Local
    type: LoadBalancer
    selector:
        app.kubernetes.io/name: ingress-nginx
        app.kubernetes.io/part-of: ingress-nginx
    ports:
        - name: http
        port: 80
        targetPort: http
        - name: https
        port: 443
        targetPort: https


https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/provider/aws/service-nlb.yaml




.. note::


cluster IP address
Multi-Port Services


.. code-block:: yaml

    kind: Service
    apiVersion: v1
    metadata:
    name: my-crossbar
    spec:
    selector:
        app: MyCrossbar
    ports:
    - name: http
        protocol: TCP
        port: 80
        targetPort: 8080
    - name: https
        protocol: TCP
        port: 443
        targetPort: 8443


.. code-block:: yaml

    apiVersion: extensions/v1beta1
    kind: Ingress
    metadata:
    name: cafe-ingress-nginx
    annotations:
        kubernetes.io/ingress.class: "nginx"
    spec:
    tls:
    - hosts:
        - cafe.example.com
        secretName: cafe-secret
    rules:
    - host: cafe.example.com
        http:
        paths:
        - path: /tea
            backend:
            serviceName: tea-svc
            servicePort: 80
        - path: /coffee
            backend:
            serviceName: coffee-svc
            servicePort: 80

https://github.com/nginxinc/kubernetes-ingress/tree/master/examples/multiple-ingress-controllers
https://github.com/nginxinc/kubernetes-ingress/blob/master/docs/installation.md
https://github.com/nginxinc/kubernetes-ingress/tree/master/examples/complete-example



"Kubernetes will create an Ingress controller pod on every node of the cluster."

https://github.com/nginxinc/kubernetes-ingress/blob/master/docs/installation.md#32-create-a-daemonset
https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/


"To access the Ingress controller, use those ports and an IP address of any node .."

"Use the public IP of the load balancer to access the Ingress controller."

https://github.com/nginxinc/kubernetes-ingress/blob/master/docs/installation.md#42-service-with-the-type-loadbalancer

"For the nginxinc/kubernetes-ingress Ingress controller its Docker image is
published on DockerHub and available as nginx/nginx-ingress."

https://github.com/nginxinc/kubernetes-ingress/blob/master/docs/nginx-ingress-controllers.md