FROM public.ecr.aws/lambda/python:3.12
LABEL maintainer="contact@wookingwoo.com"

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r requirements.txt

# Copy all codes
COPY . ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "lambda_function.handler" ]

# docker build --platform linux/amd64 -t docker-image:test .
