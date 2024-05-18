# import pickle
# import uuid
from boto3.session import Session
from botocore.client import BaseClient
from logging import Logger
from pathlib import Path
from pypomes_core import (
    APP_PREFIX, TEMP_DIR,
    env_get_str, env_get_path
)
from typing import Final
# from unidecode import unidecode

S3_BUCKET_NAME: Final[str] = env_get_str(f"{APP_PREFIX}_S3_BUCKET_NAME")
S3_ACCESS_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_S3_ACCESS_KEY")
S3_SECRET_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_S3_SECRET_KEY")
S3_ENDPOINT_URL: Final[str] = env_get_str(f"{APP_PREFIX}_S3_ENDPOINT_URL")
S3_TEMP_PATH: Final[Path] = env_get_path(f"{APP_PREFIX}_S3_TEMP_PATH", TEMP_DIR)


def s3_access(errors: list[str],
              logger: Logger = None) -> BaseClient:
    """
    Obtain and return a *S3* client object.

    :param errors: incidental error messages
    :param logger: optional logger
    :return: the S3 client object
    """
    # initialize the return variable
    result: BaseClient | None = None

    try:
        result = Session().client(service_name="s3",
                                  aws_access_key_id=S3_ACCESS_KEY,
                                  aws_secret_access_key=S3_SECRET_KEY,
                                  endpoint_url=S3_ENDPOINT_URL)
    except Exception as e:
        errors.append(str(e))
        logger.debug(e)

    return result
