import boto3

import json
import logging

# For Cisco teams
import urllib.request
import urllib.parse
import os

# set logger
logger = logging.getLogger()
logger.setLevel(os.environ['LOG_LEVEL'])

headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Authorization": "Bearer " + os.environ["CiscoTeamsAccessToken"]
}


def lambda_handler(event, context):
    logging.info(json.dumps(event))

    body = json.loads(event['body'])
    data = body['data']
    logging.info("data: {}".format(json.dumps(data, indent=4, ensure_ascii=False)))
    # Get Attachment Action Details
    attachment_action = get_attachment_action_details(data['id'])
    user = get_person_details_from_webexteams(data['personId'])
    logging.info("attachment_action: {}".format(json.dumps(attachment_action, indent=4, ensure_ascii=False)))

    # Prepare data
    payload = {
        "UserId": data['personId'],
        "MessageId": data['messageId'],
        "AttachmentId": data['id'],
        "Answers": attachment_action['inputs'],
        "RoomId": data['roomId'],
        "CreatedTime": data['created'],
        "PersonEmail": user['emails'][0]
    }
    logging.info("payload: {}".format(json.dumps(payload, indent=4, ensure_ascii=False)))

    # Write Dynamo DB
    write_to_dynamodb_table(payload, os.environ['DYNAMODB_TABLENAME'])
    delete_message_from_webexteams(data['messageId'])
    send_message_to_webexteams(user['emails'][0], "The answer has been sent.  \nThank you for your cooperation.")

    return {
        'statusCode': 200,
        'body': json.dumps(payload)
    }


def get_person_details_from_webexteams(id: str):
    url = "https://webexapis.com/v1/people/" + id
    req = urllib.request.Request(url, data={}, method="GET", headers=headers)
    with urllib.request.urlopen(req) as f:
        result = json.load(f)

    return result


def delete_message_from_webexteams(id: str):
    url = "https://webexapis.com/v1/messages/" + id
    req = urllib.request.Request(url, method="DELETE", headers=headers)
    urllib.request.urlopen(req)
    return


def send_message_to_webexteams(personEmail: str, markdown: str):
    url = "https://webexapis.com/v1/messages/"
    data = {
        "toPersonEmail": personEmail,
        "markdown": markdown
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    with urllib.request.urlopen(req) as f:
        result = json.load(f)
    return result


def get_attachment_action_details(id: str):
    url = "https://webexapis.com/v1/attachment/actions/" + id

    req = urllib.request.Request(url, data={}, method="GET", headers=headers)
    with urllib.request.urlopen(req) as f:
        result = json.load(f)
    return result


def write_to_dynamodb_table(data: dict, tablename: str):
    dynamoDB = boto3.resource("dynamodb")
    table = dynamoDB.Table(tablename)

    # Put DynamoDB
    table.put_item(
        Item=data
    )
    return
