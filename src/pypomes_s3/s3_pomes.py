from logging import Logger
from pathlib import Path
from typing import Any

from .s3_common import (
    _S3_ENGINES, _S3_ACCESS_DATA, _assert_engine
)


def db_setup(engine: str,
             access_key: str,
             access_secret: str,
             bucket_name: str,
             temp_path: str | Path,
             region_name: str = None,
             endpoint_url: str = None,
             secure_access: bool = None) -> bool:
    """
    Establish the provided parameters for access to *engine*.

    The meaning of some parameters may vary between different database engines.
    All parameters, with the exception of *db_client* and *db_driver*, are required.
    *db_client* may be provided for *oracle*, but not for the other engines.
    *db_driver* is required for *sqlserver*, but is not accepted for the other engines.

    :param engine: the S3 engine (one of [aws, minio])
    :param access_key: the access key for the service
    :param access_secret: the access secret code
    :param bucket_name: the name of the default bucket
    :param temp_path: path for temporary files
    :param region_name: the name of the region where the engine is located (AWS only)
    :param endpoint_url: the access URL for the service (MinIO only)
    :param secure_access: whether or not to use Transport Security Layer (MinIO only)
    :return: True if the data was accepted, False otherwise
    """
    # initialize the return variable
    result: bool = False

    # are the parameters compliant ?
    if (engine in ["aws", "minio"] and
        access_key and access_secret and bucket_name and temp_path and
        not (engine != "aws" and region_name) and
        not (engine == "aws" and not region_name) and
        not (engine != "minio" and endpoint_url) and
        not (engine == "minio" and not endpoint_url) and
        not (engine != "minio" and secure_access is not None) and
        not (engine == "minio" and secure_access is None)):
        _S3_ACCESS_DATA[engine] = {
            "access-key": access_key,
            "access-secret": access_secret,
            "bucket-name": bucket_name,
            "temp-path": temp_path
        }
        if engine == "aws":
            _S3_ACCESS_DATA[engine]["region-name"] = region_name
        elif engine == "minio":
            _S3_ACCESS_DATA[engine]["endpoint-url"] = endpoint_url
            _S3_ACCESS_DATA[engine]["secure-access"] = secure_access
        if engine not in _S3_ENGINES:
            _S3_ENGINES.append(engine)
        result = True

    return result


def s3_get_engines() -> list[str]:
    """
    Retrieve and return the list of configured engines.

    This list may include any of the supported engines:
     *aws*, *minio*.

    :return: the list of configured engines
    """
    return _S3_ENGINES


def db_get_params(engine: str = None) -> dict:
    """
    Return the connection parameters a *dict*.

    The returned *dict* contains the keys *name*, *user*, *pwd*, *host*, *port*.
    The meaning of these parameters may vary between different database engines.

    :param engine: the database engine
    :return: the current connection parameters for the engine
    """
    curr_engine: str = _S3_ENGINES[0] if not engine and _S3_ENGINES else engine
    return _S3_ACCESS_DATA.get(engine or curr_engine)