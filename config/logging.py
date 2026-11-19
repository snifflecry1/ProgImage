"""
Logging configuration for the project.

Used by settings.py as ``LOGGING = build_logging_config(...)``.
See https://docs.djangoproject.com/en/6.1/topics/logging/
"""


def build_logging_config(level: str = "INFO") -> dict:
    level = level.upper()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
        },
    }
