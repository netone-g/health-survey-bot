# Cisco Webex Teams Health Survey bot
A bot service for health survey implemented by Cisco Webex Teams and AWS.
Serverless Framework is used as a deployment tool.
https://www.serverless.com/

Public Cloud Provider: AWS  
Function Runtime: Python3.8

## Install
### Prepare Webex Teams Bot
1. Create a bot according to the official documentation.  
https://developer.webex.com/docs/bots  
1. Make a note of the access token of the created bot.

### Prepare a linux instance for deployment
You need a linux instance to deploy. 
- Confirmed OS version
    - ``CentOS Linux release 7.5.1804 (Core) ``
- Required library
    - curl
    - python
    - git

### Node.js Install
To use Serverless Framework, you need to install Node.js on your linux instance for deployment.
```sh
# nvm(Node.js version management tool) Run the installation script
curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash
source ~/.bashrc

# Node.js + npm Install
nvm install --lts
nvm use --lts

# Confirm the version
node -v
```

### Serverless Framework Install
```sh
npm install -g serverless
```

### Registering credentials for AWS
```sh
serverless config credentials --provider aws --key <IAMUSERACCESSKEY> --secret <IAMUSERSECRET>
# Confirm
cat ~/.aws/credentials
```

### Clone repository
```sh
cd <working directory>
git clone <repositoryURL>
cd health-survey-bot
```

## setting file
### serverless.yml
Serverless Framework configuration file.
Set environment variables etc. that are expanded on the Lambda execution environment.
```yml
...
# Provider, Function Runtime
provider:
  name: aws
  runtime: python3.8

  # Set environment variables that are deployed in the Lambda runtime environment
  environment:
    # An access token for Cisco Webex TeamsBot that submits a health survey confirmation form.
    CiscoTeamsAccessToken: <Webex Teams Bot ACCESSTOKEN>
    # DynamoDB table name to save answer results (default is service name)
    DYNAMODB_TABLENAME: <TABLENAME>
    # S3 bucket name to save past answer results (default is service name)
    S3_BUCKETNAME: <BUCKETNAME>
    # TimeZone
    TZ: 'Asia/Tokyo'
...
```

### card_settings.json
configuration file for the question form sent to the recipient.

```json
{
    // Form Title
    "title": "COVID-19 Measures Health Survey",
    // Form Overview
    "description":"It is request from the COVID-19 Countermeasures Headquarters. Please answer the following questions to ensure your safety.",
    "questions": [
        // The definition of the question.
        // Repeat the following elements for the number of questions.
        {
            // Question Title
            "title": "As a result of temperature measurement, it is 37.5 ° C or higher.",
            // Choices
            "choices": [
                {
                    // Display text of choices
                    "title": "NO",
                    // Value sent when a choice is selected
                    "value": "false"
                },
                {
                    "title": "YES",
                    "value": "true"
                },
                {
                    "title": "I don't have a thermometer.",
                    "value": "none"
                }
            ]
        },
    ...
    ]
}
```

### organizations.json
This is an organization setting file.
For name, specify the organization name in string format.
For users, specify the ID used by Webex Teams to which the form is submitted in list format.
For admins, specify the ID used by Webex Teams, an administrator who has permission to view the response results of that organization, in a list format.
```json
[
    {
        "name": "OrgA",
        "admins": [
            "a-admin@netone.local",
            "admin@netone.local"
        ],
        "users": [
            "a-user1@netone.local",
            "a-user2@netone.local",
            "a-user3@netone.local"
        ]
    },
    {
        "name": "OrgB",
        "admins": [
            "b-admin@netone.local"
        ],
        "users": [
            "b-user1@netone.local",
            "b-user2@netone.local",
            "b-user3@netone.local"
        ]
    }
]
...
```

## Deploy
### Deploy to AWS
Staging allows you to create multiple environments.
#### Deploy to default stage (dev)
```sh
sls deploy
```
If the stage is omitted, it will be as follows.
```sh
sls deploy --stage=dev
```
#### Deploy to production environment
```sh
sls deploy --stage=prod
```

### Register Webhooks with Cisco Webex Teams (only after initial deployment)
**You only need to register for a Cisco Webex Teams webhook after the initial deployment.**  
```
sls invoke -f create_webhook
```

## Default specifications
This is the default specification for each.
Each setting can be changed in the configuration file. 
"<Stage>"changes depending on the value of the --stage option at the time of deployment.
### AWS Lambda
- health-survey-<stage>-sender  
    - Lambda function for submitting question forms
    - Trigger
        - Amazon Cloud Watch Events cron format. Run every Thursday at 9am (JST)
            ```yml
            # serverless.yml
            ...
            # Set in -9 hours considering TZ +0900
            - schedule: cron(0 0 ? * THU *)
            ...
            ```
    - Handler
        - lambda_handler
    - Execution timeout
        - 300 sec

- health-survey-<stage>-reciever
    - Lambda function for receiving replies from recipients
    - Trigger
        - POST API Gateway "<stage>-health-survey" /survey endpoint
    - Handler
        - lambda_handler
    - Execution timeout
        - 30 sec

- health-survey-<stage>-status
    - Lambda function for non-execution confirmation
    - Trigger
        - POST API Gateway "<stage>-health-survey" /check endpoint
        - Amazon Cloud Watch Events cronformat. Run every Thursday at 12am (JST)
            ```yml
            # serverless.yml
            ...
            - schedule: cron(0 3 ? * THU *)
            ```
    - Handler
        - lambda_handler
    - Execution timeout
        - 30 sec

- health-survey-<stage>-create_webhook
    - Lambda function for webhook registration
    - Trigger
        - None（Manual）
    - Handler
        - lambda_handler
    - Execution timeout
        - 300 sec

### Amazon API Gateway
- <stage>-health-survey
    - /survey
        - Webhook endpoint when performing Attachment action on Webex Teams
        - Method
            - POST
        - APIKEY
            - Unnecessary
    - /check
        - - Webhook endpoint when creating a Message for Webex Teams
        - Method
            - POST
        - APKEY
            - Unnecessary

### Amazon DynamoDB
- health-survey-<stage>
    - Table for storing day answers sent by recipients
    - Primary partition key	
        - PersonEmail (string)  
            Webex Teams User Email Address
    - Attribute
        - UserId (string)  
            Webex Teams User ID
        - MessageId (string)  
            Webex Teams Answer form message ID
        - AttachmentId (string)  
            Webex Teams Answer form Attachment (card) ID
        - RoomId (string)  
            Webex Teams Answer form destination room ID
        - CreatedTime (string)  
            Answer posting time
        - Answers (map)  
            Answer form data
    - The data in the table will be exported in text format to the S3 bucket described later on the same day when the new form is submitted, and all the data will be deleted.


### Amazon S3
- health-survey-<stage>
    - Bucket for storing past day's answers sent by recipients
    - Storage file name format
        - YYYY-mm-dd.json

### Cisco Webex Teams
- Webhooks
    - Health Survey Webhook: Attachment action created
        - Webhook sent when a user fills out a form
    - Health Survey Webhook: Message created
        - Webhook sent when a user sends a one-to-one room message to a bot
