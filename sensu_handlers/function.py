import argparse
import aws_lambda_logging
import boto3
import collections
import os
import pathlib
import logging
import requests
import json

from aws_typings import LambdaContext
from aws_typings import LambdaDict
from typing import List, Dict, Any

from botocore.config import Config

log = logging.getLogger(__name__)

config = Config(retries={"max_attempts": 30, "mode": "standard"})

pagerduty_api_token = os.getenv("pagerduty_api_token", "")


def aws_logger_config(
    action: str, event: LambdaDict, context: LambdaContext, **kwargs: str
) -> None:
    """ Sets up aws logging, setting log levels and additional fields """
    aws_lambda_logging.setup(
        level=os.environ.get("log_level", "INFO"),
        boto_level=os.environ.get("boto_level", "WARN"),
        aws_request_id=context.aws_request_id,
        action=action,
        tags="sensu_handlers",
        **kwargs,
    )


def get_all_pd_services_integrations(
    offset: int = 0,
) -> List[Dict[str, List[Dict[Any, Any]]]]:
    params = {"limit": 100, "offset": offset}
    response = requests.get(
        "https://api.pagerduty.com/services",
        params=params,
        headers={
            "Authorization": "Token token=" + pagerduty_api_token,
            "Accept": "application/vnd.pagerduty+json;version=2",
        },
    )
    if response.status_code != 200:
        if response.status_code == 401:
            log.error(
                "Received 401 Unauthorised from pagerduty API. Check your pagerduty API token"
            )
        else:
            log.error(
                f"Unexpected response from pagerduty API with status code {response.status_code}"
            )
        raise SystemExit(1)

    content = response.json()
    services = [{"integrations": s["integrations"]} for s in content["services"]]
    if content["more"]:
        services += get_all_pd_services_integrations(offset + 100)
    return services


def get_pd_integration_keys(
    services: List[Dict[str, List[Dict[Any, Any]]]], env: str = "production"
):
    pagerduty_session = requests.Session()
    pagerduty_session.headers.update(
        {
            "Authorization": "Token token=" + pagerduty_api_token,
            "Accept": "application/vnd.pagerduty+json;version=2",
        }
    )
    handler_keys = {}
    for service in services:
        for integration in service["integrations"]:
            response = pagerduty_session.get(integration["self"])
            if response.status_code != 200:
                if response.status_code == 401:
                    log.error(
                        "Received 401 Unauthorised from pagerduty API. Check your pagerduty API token"
                    )
                else:
                    log.error(
                        f"Unexpected response from pagerduty API with status code {response.status_code}"
                    )
                raise SystemExit(1)
            ig = response.json()["integration"]
            if ig["type"] not in [
                "event_transformer_api_inbound_integration",
                "pingdom_inbound_integration",
                "generic_email_inbound_integration",
            ]:
                if ":" in ig["summary"]:
                    summary = ig["summary"].split(":")
                    if summary[1] == env:
                        handler_keys.update(
                            {summary[0]: {"api_key": ig["integration_key"]}}
                        )
                else:
                    handler_keys.update(
                        {ig["summary"]: {"api_key": ig["integration_key"]}}
                    )
    return collections.OrderedDict(sorted(handler_keys.items()))


def save_handler_keys(handler_keys):
    pathlib.Path("./output").mkdir(parents=True, exist_ok=True)
    with open("output/handler_keys.json", "w+") as handler_file:
        handler_file.write(json.dumps(handler_keys, indent=2, sort_keys=True))


def get_pagerduty_api_token():
    ssm = boto3.client("ssm", config=config)
    retrieve_api_token = ssm.get_parameter(
        Name=os.environ.get("PAGERDUTY_TOKEN_LOCATION"), WithDecryption=True
    )
    return retrieve_api_token["Parameter"]["Value"]


def lambda_handler(event: LambdaDict, context: LambdaContext) -> None:
    aws_logger_config("Cancel Deployment", event, context)

    environment = os.environ.get("ENVIRONMENT", "production")
    global pagerduty_api_token
    pagerduty_api_token = get_pagerduty_api_token()

    services = get_all_pd_services_integrations()
    handler_keys = get_pd_integration_keys(services, environment)

    save_handler_keys(handler_keys)


# if __name__ == "__main__":
#     services = get_all_pd_services_integrations()
#     handler_keys = get_pd_integration_keys(services, "production")
#
#     save_handler_keys(handler_keys)
