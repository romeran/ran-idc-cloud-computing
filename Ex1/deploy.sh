#!/usr/bin/env bash

echo "Initiating deployment of Parking Lot Serverless Application - using AWS SAM"

echo "Creating app persistence layer - Dynamo DB Table"
#aws dynamodb create-table \
#    --table-name ParkingLotTable \
#    --attribute-definitions \
#        AttributeName=TicketId,AttributeType=S \
#    --key-schema \
#        AttributeName=TicketId,KeyType=HASH \
#    --provisioned-throughput \
#        ReadCapacityUnits=1,WriteCapacityUnits=1

echo "Successfully created table"

echo "Deploying AWS Sam based Serverless application"
cd parking-lot-app
sam build && sam deploy --stack-name parking-lot-app --no-confirm-changeset