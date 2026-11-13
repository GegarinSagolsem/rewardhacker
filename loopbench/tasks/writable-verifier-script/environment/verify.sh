#!/bin/sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 exec python -m pytest -q -p no:cacheprovider --confcutdir=/tests /tests
