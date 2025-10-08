#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source ${SCRIPT_DIR}/mcp_env/bin/activate 
PYTHONPATH=${SCRIPT_DIR} python -m mcp_server.cpp_mcp_server


