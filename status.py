import boto3

import json
import logging

# For Cisco teams
import urllib.request
import urllib.parse
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# set logger
logger = logging.getLogger()
logger.setLevel(os.environ['LOG_LEVEL'])

headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Authorization": "Bearer " + os.environ["CiscoTeamsAccessToken"]
}


def lambda_handler(event, context):
    logging.info(json.dumps(event))
    with open("organizations.json") as f:
        organizations = json.load(f)
    dbresult = read_dynamodb_all()

    results = []

    if event.get("source") == "aws.events":
        # Schedule time
        shceduled_time = datetime.fromisoformat(event["time"].rstrip("Z")).replace(tzinfo=timezone.utc).astimezone()
        # For all organizations
        for org in organizations:
            messages = ["## {}  \n".format(org["name"])]
            # Respondent check
            anpiret = anpi_check(org["users"], dbresult)

            if len(anpiret['yet_users']) == 0:
                messages.append(shceduled_time.strftime("%-H:%M") + "No respondents at the time")
            else:
                messages.append(shceduled_time.strftime("%-H:%M") + "Unanswered at the time: " + str(convert_emails_to_display_names(anpiret['yet_users'])))
            for admin_email in org["admins"]:
                try:
                    result = send_message_to_webexteams(admin_email, "  \n".join(messages))
                except urllib.error.HTTPError as e:
                    error = json.loads(e.read())
                    logger.warning("Send a message to webex error: email={} code={} message={}".format(admin_email, e.code, error["message"]))
                else:
                    results.append(result)
    else:
        body = json.loads(event['body'])
        data = body['data']
        logging.info("data: {}".format(json.dumps(data, indent=4, ensure_ascii=False)))

        email = data['personEmail']
        message_id = data['id']

        # helpmessage
        help_message = "Enter "check" to get a list of users who have not reported their safety.  \Enter "list" to see all the answers"

        # Webex Teams Message decode
        mess_ret = get_message_from_webexteams(message_id)
        original_message = mess_ret['text']

        # Sender filters by administrator's organization
        target_orgs = filter_organization_by_admin_email(organizations, email)
        if not target_orgs:
            # No organization
            return

        if original_message == "help":
            results.append(send_message_to_webexteams(email, help_message))
        elif original_message == "list":
            for org in target_orgs:
                filtered_dbresult = filter_dbresult_by_user_emails(dbresult, org["users"])
                if len(filtered_dbresult) > 0:
                    names = convert_emails_to_display_names([d.get('PersonEmail') for d in filtered_dbresult])
                    answers = convert_dbresults_to_messages(filtered_dbresult)
                    message = "  \n".join(["> {}  \n  \n{}".format(n, a) for n, a in zip(names, answers)])
                else:
                    message = "No answer sent"
                results.append(send_message_to_webexteams(email, "## {}  \n  \n".format(org["name"]) + message))
            results.append(send_message_to_webexteams(email, "Substitute application: <URL that is application by a representative>"))
        elif original_message == "check":
            for org in target_orgs:
                messages = ["## {}  \n".format(org["name"])]
                # Filter answers by users in your organization
                filtered_dbresult = filter_dbresult_by_user_emails(dbresult, org["users"])
                # Respondent check
                anpiret = anpi_check(org["users"], filtered_dbresult)
                logger.info("anpiret: {}".format(json.dumps(anpiret, indent=4)))

                if len(anpiret['yet_users']) == 0:
                    # If all have answered
                    messages.append("No unanswered")
                else:
                    messages.append("Unanswered: " + str(convert_emails_to_display_names(anpiret['yet_users'])))

                # one or more answers
                if len(filtered_dbresult) > 0:
                    unusual_answers = anpi_check_answer(filtered_dbresult)
                    #Report if the answer is Yes
                    if unusual_answers:
                        names = convert_emails_to_display_names([a['PersonEmail'] for a in unusual_answers])
                        answers = convert_dbresults_to_messages(unusual_answers)
                        messages.extend(["> Please check {} answer  \n  \n{}".format(n, a) for n, a in zip(names, answers)])
                        messages.append("  \The health of other responded users is okay")
                    else:
                        messages.append("The health of the respondent users is okay")
                message = "  \n".join(messages)
                logger.info("Message size: {} bytes".format(len(message.encode("utf-8"))))
                results.append(send_message_to_webexteams(email, message))
            results.append(send_message_to_webexteams(email, "Substitute application: <URL that is application by a representative>"))
        else:
            results.append(send_message_to_webexteams(email, help_message))
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }


def get_message_from_webexteams(id: str):
    ciscourl = "https://webexapis.com/v1/messages/" + id

    req = urllib.request.Request(ciscourl, data={}, method="GET", headers=headers)
    result = json.load(urllib.request.urlopen(req))
    return result


def read_dynamodb_all():
    dynamoDB = boto3.resource("dynamodb")
    table = dynamoDB.Table(os.environ['DYNAMODB_TABLENAME'])  # DynamoDB Table Name

    # Get All Record from DynamoDB
    result = table.scan()
    return result.get("Items", [])


def send_message_to_webexteams(personEmail: str, markdown: str):
    url = "https://webexapis.com/v1/messages/"
    data = {
        "toPersonEmail": personEmail,
        "markdown": markdown
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    result = json.load(urllib.request.urlopen(req))
    return result


def convert_emails_to_display_names(emails: list):
    def _get(email):
        ciscourl = "https://webexapis.com/v1/people/?email=" + email
        req = urllib.request.Request(ciscourl, method="GET", headers=headers)
        r = json.load(urllib.request.urlopen(req))
        if len(r['items']) > 0:
            return r['items'][0]['displayName']
        else:
            return email

    with ThreadPoolExecutor(max_workers=10) as executor:
        result = executor.map(_get, emails)
    return list(result)


def anpi_check(users, dbresult):
    # read Dynamo DB ALL
    done_users = sorted([d.get('PersonEmail') for d in dbresult])

    # Unanswerd User:Send user list ≠ done_users
    # set to list & Alphabet sort
    yet_users = sorted(set(users) ^ (set(users) & set(done_users)))

    return {
        'yet_users': yet_users,
        'done_users': done_users
    }


def anpi_check_answer(dbresult):
    results = []
    # read Dynamo DB ALL
    for report in dbresult:
        if any([a != "false" for a in report['Answers'].values()]):
            results.append(report)
    return results


def filter_organization_by_admin_email(organizations, admin_email):
    return list(filter(lambda v: admin_email in v["admins"], organizations))


def filter_dbresult_by_user_emails(dbresult, user_emails):
    return list(filter(lambda v: v.get("PersonEmail") in user_emails, dbresult))


def create_choices_dict_list(card_settings):
    def _bold_title(value, title):
        return "**{}**".format(title) if value != "false" else title
    choices_dict_list = []
    for q in card_settings["questions"]:
        choices_dict_list.append({c["value"]: _bold_title(c["value"], c["title"]) for c in q["choices"]})
    return choices_dict_list


def convert_dbresults_to_messages(data):
    with open("card_settings.json") as f:
        card_settings = json.load(f)
    choices_dict_list = create_choices_dict_list(card_settings)

    answers_list = [d.get('Answers') for d in data]
    messages = []
    for answers in answers_list:
        _answers = ["{}: {}".format(item[0].upper(), choices_dict.get(item[1])) for item, choices_dict in zip(answers.items(), choices_dict_list)]
        messages.append("  \n".join(_answers))
    return messages
