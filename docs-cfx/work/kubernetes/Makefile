##############################################################################
#	Makefile to build and deploy CFC and FX for Kubernetes Clusters          #
##############################################################################

.PHONY: check-env all undeploy-master undeploy-edge ssh-master ssh-edge build-master build-edge \
		install-edge update-edge package

all:
	@echo
	@echo '** Please select a valid target **'
	@echo

check-env:
ifndef MAILGUN_FROM
	$(error MAILGUN_FROM is undefined!, should be: "name" <email>)
endif
ifndef MAILGUN_URL
	$(error MAILGUN_URL is undefined, should be https://api.mailgun.net/v3/..your domain../messages)
endif
ifndef MAILGUN_KEY
	$(error MAILGUN_KEY is undefined, needs to be a valid API key)
endif

REPO=crossbar-charts
SERVICE-EDGE=fx
SERVICE-MASTER=cfc
APP-MASTER=master
APP-EDGE=edge
IMAGE-MASTER=eu.gcr.io/cfcfx-212110/cfc
IMAGE-EDGE=eu.gcr.io/cfcfx-212110/fx
POD-MASTER=`kubectl get pods --namespace default -l "app=router,release=${SERVICE-MASTER}" -o jsonpath="{.items[0].metadata.name}")`
POD-EDGE=`kubectl get pods --namespace default -l "app=${APP-EDGE},release=${SERVICE-EDGE}" -o jsonpath="{.items[0].metadata.name}")`

FLAGS-MASTER=--set image.repository="${IMAGE-MASTER}" \
	--set mailgun.key="${MAILGUN_KEY}" \
	--set mailgun.from="${MAILGUN_FROM}" \
	--set mailgun.url="${MAILGUN_URL}"

FLAGS-EDGE=--set image.repository="${IMAGE-EDGE}" \
	--set mailgun.key="${MAILGUN_KEY}" \
	--set mailgun.from="${MAILGUN_FROM}" \
	--set mailgun.url="${MAILGUN_URL}"

undeploy-master:
	helm delete ${SERVICE-MASTER}
	helm del --purge ${SERVICE-MASTER}

undeploy-edge:
	helm delete ${SERVICE-EDGE}
	helm del --purge ${SERVICE-EDGE}

ssh-master:
	kubectl exec -it ${POD-MASTER} -- /bin/bash

ssh-edge:
	kubectl exec -it ${POD-EDGE} -- /bin/bash

build-edge:
	docker build docker-edge -t ${IMAGE-EDGE}
	docker push ${IMAGE-EDGE}

build-master:
	docker build docker-master -t ${IMAGE-MASTER}
	docker push ${IMAGE-MASTER}

install-edge:
	helm install --name ${SERVICE-EDGE} ./${APP-EDGE} ${FLAGS-EDGE}

install-master: check-env
	helm install --name ${SERVICE-MASTER} ./${APP-MASTER} ${FLAGS-MASTER}

update-edge:
	helm upgrade ${SERVICE-EDGE} ./${APP-EDGE} --recreate-pods ${FLAGS-EDGE}

update-master: check-env
	helm upgrade ${SERVICE-MASTER} ./${APP-MASTER} --recreate-pods ${FLAGS-MASTER}

package:
	helm package ${APP-MASTER}
	helm package ${APP-EDGE}
	helm repo index .

deploy: check-env
	gcloud container clusters get-credentials demo --region europe-west4-a
	kubectl create clusterrolebinding user-admin-binding --clusterrole=cluster-admin --user=$(gcloud config get-value account)
	kubectl create serviceaccount tiller --namespace kube-system
	kubectl create clusterrolebinding tiller-admin-binding --clusterrole=cluster-admin --serviceaccount=kube-system:tiller
	kubectl create clusterrolebinding --clusterrole=cluster-admin --serviceaccount=default:default concourse-admin
	helm init --service-account=tiller
	@echo 'Waiting for Tiller to become live ...'
	@sleep 20
	helm update
	helm install stable/etcd-operator --name cfc-etcd
	@echo 'Waiting for Etcd to stablise ...'
	@sleep 20
	kubectl apply -f yaml/etcd.yaml
	helm repo add crossbar-charts https://crossbar-charts.storage.googleapis.com/cfc/
	@echo 'Waiting for etcd to come live ...'
	@sleep 30
	helm install --name ${SERVICE-EDGE} ${REPO}/${APP-EDGE} ${FLAGS-EDGE}
	helm install --name ${SERVICE-MASTER} ${REPO}/${APP-MASTER} ${FLAGS-MASTER}
