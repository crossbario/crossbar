#!/bin/bash

docker rmi -f $(docker images -q crossbario/crossbar* | uniq)
