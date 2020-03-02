import json
from unittest import mock

import pytest

import sensu_handlers as sh


@pytest.fixture
def sns_message():
    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:eu-west-2:123:ExampleTopic",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
                    "TopicArn": "arn:aws:sns:eu-west-2:123456789012:ExampleTopic",
                    "Subject": "example subject",
                    "Message": "StackId='arn:aws:cloudformation:eu-"
                    "west-2:150648916438"
                    ":stack/ecs-platform-status-backend-protected/65676050-2"
                    "8a5-11ea-be24-021ebf3a767c'\nTimestamp='2020-01-08T10:3"
                    "9:13.051Z'\nEventId='1c625b00-3203-11ea-be24-021ebf3a76"
                    "7c'\nLogicalResourceId='ecs-platform-status-backend-pro"
                    "tected'\nNamespace='150648916438'\nPhysicalResourceId='"
                    "arn:aws:cloudformation:eu-west-2:150648916438:stack/ecs-"
                    "platform-status-backend-protected/65676050-28a5-11ea-be2"
                    "4-021ebf3a767c'\nPrincipalId='AROASGE3ABHLHCUY447XL:ecs-"
                    "mdtp-deployer-protected'\nResourceProperties='null'\nRes"
                    "ourceStatus='UPDATE_IN_PROGRESS'\nResourceStatusReason='"
                    "User Initiated'\nResourceType='AWS::CloudFormation::Stac"
                    "k'\nStackName='ecs-platform-status-backend-protected'\nC"
                    "lientRequestToken='null'\n",
                    "Timestamp": "1970-01-01T00:00:00.000Z",
                    "SignatureVersion": "1",
                    "Signature": "EXAMPLE",
                    "SigningCertUrl": "EXAMPLE",
                    "UnsubscribeUrl": "EXAMPLE",
                    "MessageAttributes": {
                        "Test": {"Type": "String", "Value": "TestString"},
                        "TestBinary": {"Type": "Binary", "Value": "TestBinary"},
                    },
                },
            }
        ]
    }


def test_lambda_handler(sns_message, caplog):
    slh.lambda_handler(sns_message, mock.Mock())
    log_message = json.loads(caplog.records[0].msg)
    assert "ResourceStatus" in log_message
    assert log_message["ResourceStatus"] == "UPDATE_IN_PROGRESS"
    assert log_message["TopicArn"] == "arn:aws:sns:eu-west-2:123456789012:ExampleTopic"
    assert log_message["Subject"] == "example subject"


def test_lambda_handler_empty_event():
    slh.lambda_handler({}, mock.Mock())


@pytest.mark.parametrize(
    "stackname,service,zone",
    [
        (
            "ecs-platform-status-backend-protected",
            "platform-status-backend",
            "protected",
        ),
        ("ecs-hello-flask-public-public", "hello-flask-public", "public"),
        (
            "ecs-hello-flask-protected-protected-rate",
            "hello-flask-protected",
            "protected-rate",
        ),
        (
            "ecs-platform-status-frontend-public-rate",
            "platform-status-frontend",
            "public-rate",
        ),
        ("ecs-service-public-monolith", "service", "public-monolith"),
    ],
)
def test_extract_zone_and_servicename_from_stackname(stackname, service, zone):
    service, zone = slh.extract_zone_and_servicename_from_stackname(stackname)
    assert service == service
    assert zone == zone
