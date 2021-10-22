#!/usr/bin/env bash
# For my personal development (not necessarily helpful for anyone else)
ENV="$1"
if [ ! -f ".env.secret.$ENV" ]; then
    echo bad env $ENV
    exit 1
fi

cp ".env.secret.$ENV" .env.secret
