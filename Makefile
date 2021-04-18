SHELL := /usr/bin/env bash
VENV ?= ./.aws-lambda-sensu-handlers-env
POETRY_OK := $(shell type -P poetry)
OPENSSL_OK := $(shell type -P openssl)
PYTHON_OK := $(shell type -P python)
PYTHON_VERSION := $(shell python -V | cut -d' ' -f2)
PYTHON_REQUIRED := $(shell cat .python-version)
BUCKET_NAME := mdtp-lambda-functions
LAMBDA_NAME := aws-lambda-sensu-handlers
ENVIRONMENTS := integration development qa staging management externaltest production

check_docker:
	@echo '********** Checking for docker installation *********'
    ifeq ('$(DOCKER_OK)','')
	    $(error package 'docker' not found!)
    else
	    @echo Found docker!
    endif

check_poetry: check_python
	@echo '********** Checking for poetry installation *********'
    ifeq ('$(POETRY_OK)','')
	    $(error package 'poetry' not found!)
    else
	    @echo Found poetry!
    endif

check_openssl:
	@echo '********** Checking for openssl installation *********'
    ifeq ('$(OPENSSL_OK)','')
	    $(error package 'openssl' not found!)
    else
	    @echo Found openssl!
    endif

check_python:
	@echo '*********** Checking for Python installation ***********'
    ifeq ('$(PYTHON_OK)','')
	    $(error python interpreter: 'python' not found!)
    else
	    @echo Found Python
    endif
	@echo '*********** Checking for Python version ***********'
    ifneq ('$(PYTHON_REQUIRED)','$(PYTHON_VERSION)')
	    $(error incorrect version of python found: '${PYTHON_VERSION}'. Expected '${PYTHON_REQUIRED}'!)
    else
	    @echo Found Python ${PYTHON_REQUIRED}
    endif

reset: ## Teardown tooling
	rm $(poetry env info --path) -r
.PHONY: reset

run: ## Run sensu_handlers
	poetry run python sensu_handlers/function.py

setup: check_poetry
	@echo '**************** Creating virtualenv *******************'
	export POETRY_VIRTUALENVS_IN_PROJECT=true && poetry run pip install --upgrade pip
	poetry install --no-root
	@echo '*************** Installation Complete ******************'

setup_git_hooks:
	@echo '****** Setting up git hooks ******'
	poetry run pre-commit install

install: setup setup_git_hooks

bumpversion:
	poetry run prepare-release

cut_release:
	poetry run cut-release

typechecking: check_python
	poetry run mypy ./sensu_handlers

black: check_poetry
	poetry run black ./sensu_handlers

security_checks:
	poetry run safety check
	poetry run bandit -r ./sensu_handlers --skip B303 --exclude ./sensu_handlers/tests/test_sensu_handlers.py

test: check_poetry typechecking security_checks
	find . -type f -name '*.pyc' -delete
	export PYTHONPATH="${PYTHONPATH}:`pwd`/sensu_handlers" && poetry run pytest ./sensu_handlers/tests

package: check_openssl
	cd sensu_handlers && zip ../${LAMBDA_NAME}.${LAMBDA_VERSION}.zip ./sensu_handlers.py
	mkdir -p pip_lambda_packages
	pip install -t pip_lambda_packages -r requirements/requirements.txt
	cd pip_lambda_packages && zip -r ../${LAMBDA_NAME}.${LAMBDA_VERSION}.zip .
	openssl dgst -sha256 -binary ${LAMBDA_NAME}.${LAMBDA_VERSION}.zip | openssl enc -base64 > ${LAMBDA_NAME}.${LAMBDA_VERSION}.zip.base64sha256
	rm -rf pip_lambda_packages

publish:
	for env in ${ENVIRONMENTS}; do \
		aws s3 cp ${LAMBDA_NAME}.$$(cat .version).zip s3://${BUCKET_NAME}-$${env}/${LAMBDA_NAME}/${LAMBDA_NAME}.$$(cat .version).zip --acl=bucket-owner-full-control ;\
		aws s3 cp ${LAMBDA_NAME}.$$(cat .version).zip.base64sha256 s3://${BUCKET_NAME}-$${env}/${LAMBDA_NAME}/${LAMBDA_NAME}.$$(cat .version).zip.base64sha256 --content-type text/plain --acl=bucket-owner-full-control ;\
	done

ci_docker_build: check_docker
	docker build -t sensu-handlers-build-env -f Dockerfile.jenkins .

ci_setup: check_docker
	docker run --user `id -u`:`id -g` -v `pwd`:/src --workdir /src sensu-handlers-build-env make clean setup

ci_test: check_docker
	docker run --user `id -u`:`id -g` -v `pwd`:/src --workdir /src sensu-handlers-build-env make test

ci_security_checks:
	docker run --user `id -u`:`id -g` -v `pwd`:/src --workdir /src sensu-handlers-build-env make security_checks

ci_package: check_docker
	docker run --user `id -u`:`id -g` -v `pwd`:/src --workdir /src sensu-handlers-build-env make package

ci_publish: publish

ci_bumpversion: check_docker
	export GIT_BRANCH=$(shell cat .git/_branch) && \
    export GITHUB_API_USER="${GIT_USERNAME}" && \
    export GITHUB_API_TOKEN="${GIT_PERSONAL_ACCESS_TOKEN}" && \
    docker run \
            -v `pwd`:/src \
            --workdir /src \
            -e GITHUB_API_USER \
            -e GITHUB_API_TOKEN \
            -e GIT_BRANCH \
            sensu-handlers-build-env make bumpversion

ci: ci_docker_build ci_setup ci_test ci_security_checks ci_bumpversion ci_package ci_publish
