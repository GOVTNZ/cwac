# Get node_modules
FROM --platform=linux/amd64 node:slim AS node_modules_builder

WORKDIR /usr/app/

# Copy package.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

FROM --platform=linux/amd64 ubuntu:noble@sha256:723ad8033f109978f8c7e6421ee684efb624eb5b9251b70c6788fdb2405d050b

# ubuntu equivalent (include upgrade)
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y wget && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get install -y \
    python3-pip \
    python3.12-venv \
    libnss3-dev  && \
    apt-get clean

# create cwac directory
WORKDIR /cwac

# copy in requirements.txt
COPY requirements-prod.txt .

# create .venv
RUN python3 -m venv .venv

ENV VIRTUAL_ENV .venv
ENV PATH .venv/bin:$PATH

# pip install
RUN python3 -m pip install --no-cache-dir -r requirements-prod.txt

# copy node_modules from node_modules_builder
COPY --from=node_modules_builder /usr/app/node_modules ./node_modules

# copy chrome binary from node_modules_builder
COPY --from=node_modules_builder /usr/app/chrome ./chrome

# copy all top-level files to /cwac/
COPY . .

# chmod +x the chromedriver
RUN chmod +x ./drivers/chromedriver_linux_x64

# create volume for ./results folder
VOLUME /cwac/results

# Create non-root user
RUN useradd -m cwac

# Ensure non-root user has write access to /cwac/results
RUN mkdir ./nltk_data/
RUN chown -R cwac:cwac ./results/
RUN chown -R cwac:cwac ./nltk_data/
RUN chmod -R 700 ./results
RUN chmod -R 700 ./nltk_data

# Change to non-root user
USER cwac

# run cwac.py config_linux.json
CMD [".venv/bin/python", "-u", "cwac.py", "config_linux.json"]