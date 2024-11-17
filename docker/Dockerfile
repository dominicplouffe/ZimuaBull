# Use a Python base image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY ./environment.prod /etc/environment
RUN apt update && apt install -y git && apt install -y supervisor;
COPY ./sup-prod.conf /etc/supervisor/conf.d/sup-prod.conf

# Expose port 8000
EXPOSE 8000
