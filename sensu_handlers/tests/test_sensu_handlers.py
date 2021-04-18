import pytest
from unittest import mock

from sensu_handlers.function import get_all_pd_services_integrations
from sensu_handlers.function import get_pagerduty_api_token
from sensu_handlers.function import get_pd_integration_keys
from sensu_handlers.function import lambda_handler
from sensu_handlers.function import save_handler_keys

from aws_typings import LambdaContext


@pytest.fixture(autouse=True)
def environ(monkeypatch):
    # contains all the required environment variables.
    data = {
        "PAGERDUTY_TOKEN_LOCATION": "/telemetry/secrets/pagerduty_api_token",
        "ENVIRONMENT": "integration",
    }
    for var_name, var_value in data.items():
        monkeypatch.setenv(var_name, var_value)


@pytest.fixture
def context():
    lambda_context = LambdaContext()
    lambda_context.aws_request_id = "aws_request_id"
    return lambda_context


@pytest.fixture
def pd_services_response_one():
    return {
        "services": [
            {
                "id": "service1",
                "integrations": [
                    {
                        "id": "P1234",
                        "type": "generic_events_api_inbound_integration_reference",
                        "summary": "serviceteam-a",
                        "self": "https://api.pagerduty.com/services/PP2A/integrations/P1234",
                    }
                ],
            }
        ],
        "more": True,
    }


@pytest.fixture
def pd_services_response_two():
    return {
        "services": [
            {
                "id": "service2",
                "integrations": [
                    {
                        "id": "P1235",
                        "type": "generic_events_api_inbound_integration_reference",
                        "summary": "serviceteam-b",
                        "self": "https://api.pagerduty.com/services/PP2B/integrations/P1235",
                    }
                ],
            }
        ],
        "more": False,
    }


@pytest.fixture
def all_integrations():
    return [
        {
            "integrations": [
                {
                    "id": "P1234",
                    "type": "generic_events_api_inbound_integration_reference",
                    "summary": "serviceteam-a",
                    "self": "https://api.pagerduty.com/services/PP2A/integrations/P1234",
                }
            ]
        },
        {
            "integrations": [
                {
                    "id": "P1235",
                    "type": "generic_events_api_inbound_integration_reference",
                    "summary": "serviceteam-b",
                    "self": "https://api.pagerduty.com/services/PP2B/integrations/P1235",
                }
            ]
        },
    ]


@pytest.fixture
def pd_get_integration_response_one():
    return {
        "integration": {
            "id": "P4N1234",
            "type": "generic_events_api_inbound_integration",
            "summary": "serviceteam-a-handler",
            "integration_key": "abc1234567890def",
        }
    }


@pytest.fixture
def pd_get_integration_response_two():
    return {
        "integration": {
            "id": "P4N1234",
            "type": "generic_events_api_inbound_integration",
            "summary": "serviceteam-b-handler",
            "integration_key": "abc1234567890ghi",
        }
    }


@pytest.fixture
def pd_get_integration_response_with_env():
    return {
        "integration": {
            "id": "P4N1234",
            "type": "generic_events_api_inbound_integration",
            "summary": "serviceteam-b-handler:integration",
            "integration_key": "abc1234567890int",
        }
    }


def test_get_all_pd_services_integrations_ok(
    pd_services_response_one, pd_services_response_two, all_integrations, mocker
):
    response_one = mock.Mock()
    response_one.status_code = 200
    response_one.json.return_value = pd_services_response_one

    response_two = mock.Mock()
    response_two.status_code = 200
    response_two.json.return_value = pd_services_response_two

    requests = mocker.patch("sensu_handlers.function.requests")
    requests.get.side_effect = [response_one, response_two]
    assert get_all_pd_services_integrations() == all_integrations


def test_get_all_pd_services_integrations_unauthorised(caplog, mocker):
    response = mock.Mock()
    response.status_code = 401
    requests = mocker.patch("sensu_handlers.function.requests")
    requests.get.return_value = response

    with pytest.raises(SystemExit):
        get_all_pd_services_integrations()

    assert (
        caplog.messages[0]
        == "Received 401 Unauthorised from pagerduty API. Check your pagerduty API token"
    )


def test_get_all_pd_services_integrations_failed_request(caplog, mocker):
    response = mock.Mock()
    response.status_code = 404
    requests = mocker.patch("sensu_handlers.function.requests")
    requests.get.return_value = response

    with pytest.raises(SystemExit):
        get_all_pd_services_integrations()

    assert (
        caplog.messages[0]
        == "Unexpected response from pagerduty API with status code 404"
    )


def test_get_pd_integration_keys_ok(
    all_integrations,
    pd_get_integration_response_one,
    pd_get_integration_response_two,
    mocker,
):
    response_one = mock.Mock()
    response_one.json.return_value = pd_get_integration_response_one
    response_one.status_code = 200
    response_two = mock.Mock()
    response_two.json.return_value = pd_get_integration_response_two
    response_two.status_code = 200

    pagerduty_session = mocker.patch("sensu_handlers.function.requests.Session")
    pagerduty_session().get.side_effect = [response_one, response_two]
    assert get_pd_integration_keys(all_integrations) == {
        "serviceteam-a-handler": {"api_key": "abc1234567890def"},
        "serviceteam-b-handler": {"api_key": "abc1234567890ghi"},
    }


def test_get_pd_integration_keys_specific_environment(
    all_integrations,
    pd_get_integration_response_one,
    pd_get_integration_response_with_env,
    mocker,
):
    response_one = mock.Mock()
    response_one.json.return_value = pd_get_integration_response_one
    response_one.status_code = 200
    response_two = mock.Mock()
    response_two.json.return_value = pd_get_integration_response_with_env
    response_two.status_code = 200

    pagerduty_session = mocker.patch("sensu_handlers.function.requests.Session")
    pagerduty_session().get.side_effect = [response_one, response_two]
    assert get_pd_integration_keys(all_integrations, "integration") == {
        "serviceteam-a-handler": {"api_key": "abc1234567890def"},
        "serviceteam-b-handler": {"api_key": "abc1234567890int"},
    }


def test_get_pd_integration_keys_unauthorised(caplog, all_integrations, mocker):
    response = mock.Mock()
    response.status_code = 401
    pagerduty_session = mocker.patch("sensu_handlers.function.requests.Session")
    pagerduty_session().get.return_value = response

    with pytest.raises(SystemExit):
        get_pd_integration_keys(all_integrations)

    assert (
        caplog.messages[0]
        == "Received 401 Unauthorised from pagerduty API. Check your pagerduty API token"
    )


def test_get_pd_integration_keys_failed_request(caplog, all_integrations, mocker):
    response = mock.Mock()
    response.status_code = 404
    pagerduty_session = mocker.patch("sensu_handlers.function.requests.Session")
    pagerduty_session().get.return_value = response

    with pytest.raises(SystemExit):
        get_pd_integration_keys(all_integrations)

    assert (
        caplog.messages[0]
        == "Unexpected response from pagerduty API with status code 404"
    )


def test_lambda_handler(context, mocker):
    mock_get_services = mocker.patch(
        "sensu_handlers.function.get_all_pd_services_integrations"
    )
    mock_get_services.return_value = []
    mock_get_keys = mocker.patch("sensu_handlers.function.get_pd_integration_keys")
    mock_save_keys = mocker.patch("sensu_handlers.function.save_handler_keys")
    mock_get_token = mocker.patch("sensu_handlers.function.get_pagerduty_api_token")
    lambda_handler({}, context)
    assert mock_get_token.called_once()
    assert mock_get_services.called_once()
    assert mock_get_keys.called_once_with([], "integration")
    assert mock_save_keys.called_once()


def test_get_pagerduty_api_token(mocker):
    mock_boto_client = mocker.patch("boto3.client")
    mock_boto_client().get_parameter.return_value = {
        "Parameter": {"Value": "api_token"}
    }
    assert get_pagerduty_api_token() == "api_token"


def test_save_handler_keys(mocker):
    keys = {
        "b-handler": {"api_key": "abc1234567890ghi"},
        "a-handler": {"api_key": "abc1234567890def"},
    }
    sorted_keys = """{
  "a-handler": {
    "api_key": "abc1234567890def"
  },
  "b-handler": {
    "api_key": "abc1234567890ghi"
  }
}"""
    mock_put_secret = mocker.patch("credstash.putSecret")
    save_handler_keys(keys)
    mock_put_secret.assert_called_once_with(
        "handler_keys", sorted_keys, context={"role": "sensu"}
    )
