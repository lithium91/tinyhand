#!/bin/sh
export PYTHONPATH="@SHARE@${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 -m tinyhand "$@"
