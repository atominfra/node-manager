#!/bin/bash
set -e

echo "Installing docker"

sudo apt-get -qq update
sudo apt-get -qq install -y ca-certificates curl git gettext-base jq make tmux
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "Add the docker repository to apt sources"

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get -qq update

sudo apt-get -qq install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Docker installation complete"

echo "Create a new docker network"
if ! sudo docker network inspect atominfra > /dev/null 2>&1; then
    sudo docker network create --driver bridge atominfra
fi
