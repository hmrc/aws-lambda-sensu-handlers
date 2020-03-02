import argparse
import collections
import credstash
import os
import logging
import requests
import json
import aws_lambda_logging

log = logging.getLogger(__name__)


def get_pd_services(pd_session, offset=0):
    params = {"limit": 100, "offset": offset}
    response = pd_session.get("https://api.pagerduty.com/services", params=params)
    content = json.loads(response.content)
    services = content["services"]
    log.debug(services)
    if content["more"]:
        services += get_pd_services(pd_session, offset + 100)
    return services


def get_pd_integration_keys(pd_session, services, env):
    handler_keys = {}
    for service in services:
        for integration in service["integrations"]:
            response = pd_session.get(integration["self"])
            ig = json.loads(response.content)["integration"]
            try:
                if "integration_key" in ig:
                    log.info(f"{ig}")
                    if ":" in ig["summary"]:
                        summary = ig["summary"].split(":")
                        if summary[1] == env:
                            handler_keys.update(
                                {summary[0]: {"api_key": ig["integration_key"]}}
                            )
                    else:
                        handler_keys.update(
                            {integration["summary"]: {"api_key": ig["integration_key"]}}
                        )
            except TypeError as e:
                log.info(f"ignoring non sensu integration: {ig} ({type(e)}:{e})")
    return collections.OrderedDict(sorted(handler_keys.items()))


def save_handler_keys(env):
    authorization_token = os.getenv('authorization_token')
    pagerduty_session = requests.Session()
    pagerduty_session.headers.update(
        {
            "Authorization": "Token token=" + authorization_token,
            "Accept": "application/vnd.pagerduty+json;version=2",
        }
    )

    services = get_pd_services(pagerduty_session)
    handler_keys = get_pd_integration_keys(pagerduty_session, services, env)

    log.info(json.dumps(handler_keys, indent=2))

    if not os.path.isdir("output"):
        os.mkdir("output")
    handler_file = open("output/handler_keys.json", "w+")
    handler_file.write(json.dumps(handler_keys, indent=2, sort_keys=True))
    handler_file.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e", "--env", help="Environment", default="production", type=str
    )
    args = parser.parse_args()
    save_handler_keys(args.env)
