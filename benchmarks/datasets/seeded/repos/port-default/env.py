"""Environment helpers -- a distractor for issue->code localization."""

import os


def get(name):
    return os.environ.get(name, "")
