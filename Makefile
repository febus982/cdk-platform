diff:
	cdk diff || true

deploy:
	cdk deploy "*" -O outputs.json

destroy:
	cdk destroy "*"
