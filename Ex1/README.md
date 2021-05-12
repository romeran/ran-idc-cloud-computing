# Exercise 1- Parking Lot

### Structure
There are two main parts to the submission

1. `parking-lot-app` - a Python based serverless project, created according to [AWS Sam](https://aws.amazon.com/serverless/sam/) template.
   The chosen persistence storage layer is AWS Dynamo DB.
2. `deploy.sh` - the deployment script. A prerequisite for running it is having the Sam CLI installed on the machine running the script. 
   You can find [here](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) 
   installation instructions.

### Cleanup
In order to cleanup the resources created by the application, you can use:

`aws cloudformation delete-stack --stack-name parking-lot-app --region <default-user-region>`