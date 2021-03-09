import boto3

import os
import json
import logging
import itertools
import urllib.request
import urllib.error
from datetime import datetime

# set logger
logger = logging.getLogger()
logger.setLevel(os.environ['LOG_LEVEL'])


def lambda_handler(event, context):
    logging.info(json.dumps(event))

    results = []
    with open("organizations.json") as f:
        organizations = json.load(f)
    with open("card_settings.json") as f:
        card_settings = json.load(f)

    if event.get("source") == "aws.events":
        clean_dynamodb_table(os.environ['DYNAMODB_TABLENAME'], os.environ['S3_BUCKETNAME'])

        attachments = create_attachements(card_settings)
        logger.info("organizations: {}".format(organizations))
        for o in organizations:
            for email in o["users"]:
                try:
                    result = post_attachements_to_webex(email, card_settings['title'], attachments)
                except urllib.error.HTTPError as e:
                    error = json.loads(e.read())
                    logger.warning("Send a message to webex error: email={} code={} message={}".format(email, e.code, error["message"]))
                else:
                    results.append(result)

    elif "email" in event:
        email = event["email"]
        if email not in set(itertools.chain.from_iterable([o["users"] for o in organizations])):
            logger.info("'{}' does not belong to any organization.".format(email))
            return
        logger.info("email: {}".format(email))
        attachments = create_attachements(card_settings)
        try:
            result = post_attachements_to_webex(email, card_settings['title'], attachments)
        except urllib.error.HTTPError as e:
            error = json.loads(e.read())
            logger.warning("Send a message to webex error: email={} code={} message={}".format(email, e.code, error["message"]))
        else:
            results.append(result)

    return results


def clean_dynamodb_table(tablename: str, bucketname: str):
    dynamoDB = boto3.resource("dynamodb")
    s3 = boto3.resource('s3')
    table = dynamoDB.Table(tablename)

    response = table.scan()
    table_data = response.get('Items', [])
    now = datetime.now()
    if table_data:
        obj = s3.Object(bucketname, now.strftime("%Y-%m-%d") + ".json")
        obj.put(Body=json.dumps(table_data, ensure_ascii=False))
        with table.batch_writer() as writer:
            for item in table_data:
                writer.delete_item(Key={"PersonEmail": item['PersonEmail']})
    else:
        logger.info("No survey response data for " + now.strftime("%Y-%m-%d"))
    return


def post_attachements_to_webex(target: str, markdown: str, attachments: str):
    url = "https://webexapis.com/v1/messages"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": "Bearer " + os.environ["CISCO_WEBEX_ACCESS_TOKEN"]
    }
    data = {
        "toPersonEmail": target,
        "markdown": markdown,
        "attachments": attachments
    }

    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    with urllib.request.urlopen(req) as f:
        result = json.load(f)
    return result


def create_attachements(card_settings):
    body = [
        {
            "type": "TextBlock",
            "size": "Medium",
            "weight": "bolder",
            "text": card_settings['title'],
            "wrap": True
        },
        {
            "type": "TextBlock",
            "weight": "bolder",
            "text": datetime.now().strftime("%a, %d %b %Y")
        },
        {
            "type": "TextBlock",
            "size": "Small",
            "text": card_settings['description'],
            "wrap": True

        }
    ]
    for i, q in enumerate(card_settings["questions"]):
        body.extend([
            {
                "type": "TextBlock",
                "text": q['title'],
                "wrap": True
            },
            {
                "type": "Input.ChoiceSet",
                "id": "q{}".format(i + 1),
                "style": "expanded",
                "choices": q['choices']
            }
        ])

    attachments = [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.0",
                "body": body,
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "Submit"
                    }
                ]
            }
        }
    ]
    return attachments
