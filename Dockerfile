# Get node_modules
FROM --platform=linux/amd64 node:slim AS node_modules_builder

WORKDIR /usr/app/

# Copy package.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

RUN chrome_version=$(node -p 'require("./package.json").config.chromeVersion') && \
    cp chrome/linux-${chrome_version}/chrome-linux64/chrome_sandbox /usr/local/sbin/chrome-devel-sandbox

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
COPY requirements.txt .

# create .venv
RUN python3 -m venv .venv

ENV VIRTUAL_ENV .venv
ENV PATH .venv/bin:$PATH

# pip install
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# copy node_modules from node_modules_builder
COPY --from=node_modules_builder /usr/app/node_modules ./node_modules

# copy chrome binary from node_modules_builder
COPY --from=node_modules_builder /usr/app/chrome ./chrome

# Ensure the Chrome sandbox is setup
COPY --from=node_modules_builder /usr/local/sbin/chrome-devel-sandbox /usr/local/sbin/chrome-devel-sandbox
RUN chown root:root /usr/local/sbin/chrome-devel-sandbox
RUN chmod 4755 /usr/local/sbin/chrome-devel-sandbox

ENV CHROME_DEVEL_SANDBOX /usr/local/sbin/chrome-devel-sandbox

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

RUN mkdir ./nltk_data/
RUN chown -R $USER_ID:$GROUP_ID ./nltk_data/
RUN chmod -R 700 ./nltk_data

# Change to non-root user
USER $USER_ID:$GROUP_ID

# run cwac.py config_linux.json
CMD [".venv/bin/python", "-u", "cwac.py", "config_default.json"]
