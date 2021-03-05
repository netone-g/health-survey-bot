# Cisco Webex Health Survey bot
A bot service for health survey implemented by Cisco Webex and AWS.
Serverless Framework is used as a deployment tool.
https://www.serverless.com/

Public Cloud Provider: AWS  
Function Runtime: Python3.8

## Features
- A card is sent once a day.
- Administrators can check the response status.

## Dependencies
All Python scripts in this application do not use any external libraries except standard libraries that are included in the Lambda Python 3.8 runtime. You don't need to build or include any additional modules in the Lambda package.

## Preparation
### Prepare Webex Bot
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

### Set up environment variables
'serverless.yml' is a Serverless Framework configuration file. In the 'environment' section of this file, you need to set some environment variables which will be passed to the Lambda execution environment.

The parameters that need to be prepared are as follows
- CiscoWebexAccessToken (Required)
    - Set the access token for the Webex bot you created in the 'Prepare Webex Teams Bot' section.
- DYNAMODB_TABLENAME, S3_BUCKETNAME, TZ (Optional)
    - These variables are optional. You do not need to change it to run the application, but you can change it according to your environment.

Notes: 
- No AWS credentials are required in the Lambda environment variables because the IAM role with required policies will be created and attached in the deploy step by Serverless Framework. You just need to set up credentials in your instance where you execute Serverless Framework CLI, check the 'Registering credentials for AWS' section above.
```yml
...
# Provider, Function Runtime
provider:
  name: aws
  runtime: python3.8

  # Set environment variables that are deployed in the Lambda runtime environment
  environment:
    # An access token for Cisco Webex Bot that submits a health survey confirmation form.
    CiscoWebexAccessToken: <Webex Bot ACCESSTOKEN>
    # DynamoDB table name to save answer results (default is service name)
    DYNAMODB_TABLENAME: <TABLENAME>
    # S3 bucket name to save past answer results (default is service name)
    S3_BUCKETNAME: <BUCKETNAME>
    # TimeZone
    TZ: 'UTC'
...
```

### Modify survey questions
configuration file for the question form sent to the recipient. You can change the messages in the survey card by modifying this file.
Defaults are as follows: 
```json
{
    "title": "COVID-19 Measures Health Survey",
    "description":"It is request from the COVID-19 Countermeasures Headquarters. Please answer the following questions to ensure your safety.",
    "questions": [
        {
            "title": "Please let us know your current physical condition*",
            "choices": [
                {
                    "title": "Good",
                    "value": "false"
                },
                {
                    "title": "Poor physical condition",
                    "value": "true"
                }
            ]
        },
        {
            "title": "Please let us know about the physical condition of your roommate*",
            "choices": [
                {
                    "title": "All good",
                    "value": "false"
                },
                {
                    "title": "Some people are poor condition",
                    "value": "true"
                }
            ]
        }
    ]
}
```

### Set up recipients and observers
'organizations.json' is an organization setting file. 
For 'name' attribute, specify the organization name in string format. 
For 'users' lists, specify the emails for Webex Teams  accounts to which the form is submitted in list format who receive the survey card. For 'admins' lists, specify the emails for Webex Teams  accounts who have the permission to view the response results of their organizations.
You can add the above sets of attributes in dictionary format as many as you need.
** In order to run this application, you need to add one or more existing Webex accounts to the 'users' list. **
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
If the stage is omitted, it will be same as follows.
```sh
sls deploy --stage=dev
```
#### Deploy to production environment
```sh
sls deploy --stage=prod
```

### Register Webhooks with Cisco Webex (only after initial deployment)
**You only need to register for a Cisco Webex webhook after the initial deployment.**  
```
sls invoke -f create_webhook
```

## Default specifications
This is the default specification for each.
Each setting can be changed in the configuration file. 
"{stage}"changes depending on the value of the --stage option at the time of deployment.
Amazon API Gateway, AWS Lambda, Amazon Dynamo DB, Amazon S3 may be billed based on usage.
Please refer the AWS page for details.
### AWS Lambda
- health-survey-{stage}-sender  
    - Lambda function for submitting question forms
    - Trigger
        - Amazon Cloud Watch Events cron format. Run every Thursday at 9am (JST)
        - Optionally, you need to change the Cron time according to the TimeZone.
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

- health-survey-{stage}-reciever
    - Lambda function for receiving replies from recipients
    - Trigger
        - POST API Gateway "{stage}-health-survey" /survey endpoint
    - Handler
        - lambda_handler
    - Execution timeout
        - 30 sec

- health-survey-{stage}-status
    - Lambda function for non-execution confirmation
    - Trigger
        - POST API Gateway "{stage}-health-survey" /check endpoint
        - Amazon Cloud Watch Events cronformat. Run every Thursday at 12am (JST)
        - Optionally, you need to change the Cron time according to the TimeZone.
            ```yml
            # serverless.yml
            ...
            - schedule: cron(0 3 ? * THU *)
            ```
    - Handler
        - lambda_handler
    - Execution timeout
        - 30 sec

- health-survey-{stage}-create_webhook
    - Lambda function for webhook registration
    - Trigger
        - None（Manual）
    - Handler
        - lambda_handler
    - Execution timeout
        - 300 sec

### Amazon API Gateway
- {stage}-health-survey
    - /survey
        - Webhook endpoint when performing Attachment action on Webex
        - Method
            - POST
        - APIKEY
            - Unnecessary
    - /check
        - - Webhook endpoint when creating a Message for Webex
        - Method
            - POST
        - APKEY
            - Unnecessary

### Amazon DynamoDB
- health-survey-{stage}
    - Table for storing day answers sent by recipients
    - Primary partition key	
        - PersonEmail (string)  
            Webex User Email Address
    - Attribute
        - UserId (string)  
            Webex User ID
        - MessageId (string)  
            Webex Answer form message ID
        - AttachmentId (string)  
            Webex Answer form Attachment (card) ID
        - RoomId (string)  
            Webex Answer form destination room ID
        - CreatedTime (string)  
            Answer posting time
        - Answers (map)  
            Answer form data
    - The data in the table will be exported in text format to the S3 bucket described later on the same day when the new form is submitted, and all the data will be deleted.


### Amazon S3
- health-survey-{stage}
    - Bucket for storing past day's answers sent by recipients
    - Storage file name format
        - YYYY-mm-dd.json

### Cisco Webex
- Webhooks
    - Health Survey Webhook: Attachment action created
        - Webhook sent when a user fills out a form
    - Health Survey Webhook: Message created
        - Webhook sent when a user sends a one-to-one room message to a bot
