#!/bin/sh
/venv/bin/python3 /db-init.py 
touch /db-init-signal/db-init.done

# tail -f /dev/null