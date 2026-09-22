This will be a FastAPI web application implementing a Jev API as described here https://docs.typesafe.ai/api  and here https://docs.typesafe.ai/models. It should support the optional use of OTEL logging, tracing, and metrics. To start it will support either an auth or no-auth mode. It should use Pydantic for configuration. It is intended to be deployed for production workloads. It will need a Docker image with trim dependencies. This project will use uv for managing virtual environments and dependencies. Dependencies will be managed in requirements.in and dev-requirements.in files that will be compiled to .txt files. The Docker image build should have a multi stage build from an ubuntu python image and the final "production" image should not ship the development requirements.

The core inference is performed by this web service is done with https://github.com/NandhaKishorM/laya.

Documentation for this service should be created with MKDocs.

The goal of this project is to be able to use the official https://github.com/typesafe-ai/typesafe-sdk-python with this FastAPI server. Unit tests, and integration tests validating this will be required. 

This project is hosted on GitHub with access to GitHub Actions runners. CI should be implemented with GitHub Actions https://docs.github.com/en/actions. We will want linting with Ruff that does black styling, isort, and the regular ruff checks. Mypy I guess could also be warrented. Pyproject.toml Should say Drew Bednar is the author. It's Apache 2.0 licensed and the dependencies as mentioned should be managed with the requirements files I mentioned above, not contained in the pyproject.toml.

There should be a Makefile for developers to perform tasks like linting, first time development environment setup, image builds, dev image builds, etc.

There should be a way to run load tests against this project too. I have a preference for the K6s product https://k6.io/.
