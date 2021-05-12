import json
import uuid
from datetime import datetime

import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ParkingLotTable')

HOUR_CHARGE = 10
CHARGE_MINUTE_INCREMENTS = 15


def lambda_handler(event, context):
    """
    Top Level lambda API handler
    """
    response_body = {}
    if event['path'] == '/entry':
        return handle_entry(event, response_body)
    elif event['path'] == '/exit':
        return handle_exit(event, response_body)
    else:

        print("App path not configured correctly")
        return {
            "statusCode": 400,
            "body": json.dumps(response_body)
        }


def handle_exit(event, response_body):
    """
    Exit scenario
    """
    ticket_id = event['queryStringParameters']['ticketId']
    dynamo_response = table.get_item(Key={'TicketId': ticket_id})
    parking_details = dynamo_response.get('Item')

    if parking_details is None:
        return {
            "statusCode": 400,
            "body": json.dumps({'error': 'Could not find request ticket in the system'})
        }

    exit_time = datetime.now()
    entry_time = datetime.strptime(parking_details['EntryTime'], "%Y-%m-%d %H:%M:%S.%f")
    parking_time = exit_time - entry_time
    charge = _compute_charge(parking_time)

    response_body['plate'] = parking_details['Plate']
    response_body['parkingLot'] = parking_details['ParkingLot']
    response_body['totalParkedTime'] = str(parking_time)
    response_body['charge'] = str(charge)

    # delete ticket to avoid exiting with it again
    table.delete_item(Key={'TicketId': ticket_id})

    return {
        "statusCode": 200,
        "body": json.dumps(response_body)
    }


def _compute_charge(parking_time):
    parking_time_seconds = parking_time.total_seconds()
    hours, remainder = divmod(parking_time_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    increments = minutes // CHARGE_MINUTE_INCREMENTS
    charge = HOUR_CHARGE * hours + increments * (HOUR_CHARGE / CHARGE_MINUTE_INCREMENTS)
    return charge


def handle_entry(event, response_body):
    """
    Entry scenario
    """
    ticket_id = str(uuid.uuid4())
    parking_lot = event['queryStringParameters']['parkingLot']
    plate = event['queryStringParameters']['plate']

    table.put_item(
        Item={
            'ParkingLot': parking_lot,
            'Plate': plate,
            'TicketId': ticket_id,
            'EntryTime': str(datetime.now())
        })

    response_body['ticketId'] = ticket_id

    return {
        "statusCode": 200,
        "body": json.dumps(response_body)
    }
