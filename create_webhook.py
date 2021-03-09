import os
import json
import urllib.request
import logging

# set logger
logger = logging.getLogger()
logger.setLevel(os.environ['LOG_LEVEL'])

headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Authorization": "Bearer " + os.environ["CISCO_WEBEX_ACCESS_TOKEN"]
}


def lambda_handler(event, context):
    webhooks = get_webhooks()["items"]
    logger.info("Showing registered Webhooks: {}".format(json.dumps(webhooks, indent=4, ensure_ascii=False)))
    for webhook in webhooks:
        delete_webhook(webhook["id"])
        logger.info("Webhook successfully deleted: {}".format(webhook["id"]))
    if event and event.get("delete"):
        return []
    results = []
    result = create_attachment_actions_webhook(os.environ['AWS_API_GATEWAY_ROOT_URL'] + "survey")
    logger.info("Webhook successfully registered: {}".format(json.dumps(result, indent=4, ensure_ascii=False)))
    results.append(result)
    result = create_message_webhook(os.environ['AWS_API_GATEWAY_ROOT_URL'] + "check")
    logger.info("Webhook successfully registered: {}".format(json.dumps(result, indent=4, ensure_ascii=False)))
    results.append(result)
    return results


def _create_webhook(target_url, data, headers):
    url = "https://webexapis.com/v1/webhooks"
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    with urllib.request.urlopen(req) as f:
        result = json.load(f)
    return result


def create_attachment_actions_webhook(target_url):
    data = {
        "name": "Health Survey Webhook: Attachment action created",
        "targetUrl": target_url,
        "resource": "attachmentActions",
        "event": "created",
    }
    result = _create_webhook(target_url, data, headers)
    return result


def create_message_webhook(target_url):
    data = {
        "name": "Health Survey Webhook: Message created",
        "targetUrl": target_url,
        "resource": "messages",
        "event": "created"
    }
    result = _create_webhook(target_url, data, headers)
    return result


def get_webhooks():
    url = "https://webexapis.com/v1/webhooks"

    req = urllib.request.Request(url, method="GET", headers=headers)
    with urllib.request.urlopen(req) as f:
        result = json.load(f)
    return result


def delete_webhook(id):
    url = "https://webexapis.com/v1/webhooks/" + id

    req = urllib.request.Request(url, method="DELETE", headers=headers)
    return urllib.request.urlopen(req)
