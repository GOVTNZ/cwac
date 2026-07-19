# Get node_modules
FROM --platform=linux/amd64 node:22-slim AS node_modules_builder

WORKDIR /usr/app/

# Copy package.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

FROM --platform=linux/amd64 ubuntu:noble@sha256:723ad8033f109978f8c7e6421ee684efb624eb5b9251b70c6788fdb2405d050b

# ubuntu equivalent (include upgrade)
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends wget python3-pip python3.12-venv libnss3-dev libgl1 && \
    wget -nv https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y --no-install-recommends ./google-chrome-stable_current_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives && \
    rm google-chrome-stable_current_amd64.deb

# create cwac directory
WORKDIR /cwac

# create .venv
RUN python3 -m venv .venv

ENV VIRTUAL_ENV .venv
ENV PATH .venv/bin:$PATH

# copy in requirements.txt
COPY requirements.txt .

# pip install
RUN python3 -m pip install --no-cache-dir -r requirements.txt

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

# Ensure non-root user has write access to /cwac/results
# todo: try to create user & group if they do not exist?
ARG USER_ID=1000
ARG GROUP_ID=1000

RUN mkdir ./nltk_data/ && \
    chown -R $USER_ID:$GROUP_ID ./nltk_data/ && \
    chmod -R 700 ./nltk_data

# Change to non-root user
USER $USER_ID:$GROUP_ID

# run cwac.py config_linux.json
CMD [".venv/bin/python", "-u", "cwac.py", "config_default.json"]
