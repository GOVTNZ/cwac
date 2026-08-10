# Get node_modules
FROM --platform=linux/amd64 node:22-slim AS node_modules_builder

WORKDIR /usr/app/

# unzip required to install puppeteer chromedriver
RUN apt-get update && \
    apt-get install -y --no-install-recommends unzip && \
    rm -rf /var/lib/apt/lists/*

# Copy package.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

FROM --platform=linux/amd64 ubuntu:noble@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

# install the dependencies we need for running Python and Chrome, while avoiding installing
# Chrome itself since that gets managed using @puppeteer/browsers as part of the npm install
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends wget python3.12-venv libgl1 && \
    wget -nv https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get satisfy -y --no-install-recommends "$(dpkg-deb -f google-chrome-stable_current_amd64.deb Depends | tr '\n' ' ')" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives && \
    rm google-chrome-stable_current_amd64.deb

# create cwac directory
WORKDIR /cwac

# create .venv
RUN python3.12 -m venv .venv

ENV VIRTUAL_ENV=".venv" \
    PATH=".venv/bin:$PATH"

# set XDG_CONFIG_HOME and XDG_CACHE_HOME to a temporary directory to avoid
# permission issues when running Chrome in a Docker container
ENV XDG_CONFIG_HOME=/tmp/.chromium
ENV XDG_CACHE_HOME=/tmp/.chromium

# copy in requirements.txt
COPY requirements.txt .

# install dependencies, and then remove stuff we don't need when running the tool,
# along with test files as they can be quite large for dependencies like pandas
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m pip uninstall -y ruff mypy pyfakefs pytest pytest-mock pip && \
    find .venv/lib -depth -type d \( -name tests -o -name test \) -exec rm -rf -- {} +

# copy required dirs from node_modules_builder
COPY --from=node_modules_builder /usr/app/node_modules ./node_modules
COPY --from=node_modules_builder /usr/app/chrome ./chrome
COPY --from=node_modules_builder /usr/app/chromedriver ./chromedriver

# copy all top-level files to /cwac/
COPY . .

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
