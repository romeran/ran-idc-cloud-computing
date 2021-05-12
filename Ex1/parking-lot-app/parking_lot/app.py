import json
import uuid
from datetime import datetime

import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ParkingLotTable')

HOUR_CHARGE = 10
CHARGE_MINUTE_INCREMENTS = 15


def put_parking_entry(parking_lot, plate, ticket_id):
    response = table.put_item(
        Item={
            'ParkingLot': parking_lot,
            'Plate': plate,
            'TicketId': ticket_id,
            'EntryTime': str(datetime.now())
        })
    print(response)


def get_parking_details(ticket_id):
    dynamo_response = table.get_item(Key={'TicketId': ticket_id})
    return dynamo_response['Item']


def lambda_handler(event, context):
    response_body = {}
    if event['path'] == '/entry':
        ticket_id = str(uuid.uuid4())
        parking_lot = event['queryStringParameters']['parkingLot']
        plate = event['queryStringParameters']['plate']

        put_parking_entry(parking_lot, plate, ticket_id)
        response_body['ticketId'] = ticket_id

    elif event['path'] == '/exit':
        ticket_id = event['queryStringParameters']['ticketId']
        parking_details = get_parking_details(ticket_id)

        exit_time = datetime.now()
        entry_time = datetime.strptime(parking_details['EntryTime'], "%Y-%m-%d %H:%M:%S.%f")
        parking_time = exit_time - entry_time

        parking_time_seconds = parking_time.total_seconds()
        hours, remainder = divmod(parking_time_seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        increments = minutes // CHARGE_MINUTE_INCREMENTS
        charge = HOUR_CHARGE * hours + increments * (HOUR_CHARGE / CHARGE_MINUTE_INCREMENTS)

        response_body['plate'] = parking_details['Plate']
        response_body['parkingLot'] = parking_details['ParkingLot']

        response_body['totalParkedTime'] = parking_time
        response_body['charge'] = str(charge)

    else:
        raise ValueError("Unsupported path")

    return {
        "statusCode": 200,
        "body": json.dumps(response_body)
    }
