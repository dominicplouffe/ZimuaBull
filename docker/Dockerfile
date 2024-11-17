# Use a Python base image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY ./environment.prod /etc/environment
RUN set -a && . /etc/environment && set +a

# Expose port 8080
EXPOSE 8080
