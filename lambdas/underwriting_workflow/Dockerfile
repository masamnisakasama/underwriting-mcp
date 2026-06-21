FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}
COPY pyproject.toml README.md ./
COPY underwriting_core ./underwriting_core
COPY underwriting_app ./underwriting_app
COPY underwriting_mcp ./underwriting_mcp
COPY lambdas ./lambdas
COPY rulesets ./rulesets

RUN pip install --no-cache-dir ".[aws]"

CMD ["lambdas.underwriting_workflow.app.handler"]
