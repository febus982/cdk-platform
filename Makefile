######### MAIN ##########
diff:
	cdk diff || true

deploy-cluster: deploy-cdk

destroy-cluster: destroy-apps destroy-cdk
#########################

######### APPS ##########
update-kubeconfig:
	eval "python scripts/update_kubeconfig_from_cdk_output.py" | bash

deploy-apps: update-kubeconfig deploy-istio

destroy-apps: destroy-istio
#########################

######## ISTIO ##########
deploy-istio:
	${HOME}/.istioctl/bin/istioctl install -f istio/values.yaml

destroy-istio:
	${HOME}/.istioctl/bin/istioctl manifest generate -f istio/values.yaml | kubectl delete -f - || true
	kubectl delete namespace istio-system --ignore-not-found=true
#########################

####### CLUSTER #########
deploy-cdk:
	cdk deploy "*" -O outputs.json

destroy-cdk:
	cdk destroy "*" -f
#########################
