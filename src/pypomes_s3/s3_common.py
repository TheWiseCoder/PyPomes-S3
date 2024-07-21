from logging import DEBUG, Logger
from pathlib import Path
from pypomes_core import (
    APP_PREFIX,
    env_get_bool, env_get_str, str_sanitize, str_get_positional
)
from typing import Any

# - the preferred way to specify S3 storage parameters is dynamically with 's3_setup_params'
# - specifying S3 storage parameters with environment variables can be done in two ways:
#   1. specify the set
#     {APP_PREFIX}_S3_ENGINE (one of 'aws', 'ecs', 'minio')
#     {APP_PREFIX}_S3_ENDPOINT_URL
#     {APP_PREFIX}_S3_ACCESS_KEY
#     {APP_PREFIX}_S3_SECRET_KEY
#     {APP_PREFIX}_S3_BUCKET_NAME
#     {APP_PREFIX}_S3_TEMP_FOLDER
#     {APP_PREFIX}_S3_REGION_NAME (for aws)
#     {APP_PREFIX}_S3_SECURE_ACCESS (for minio)
#   2. alternatively, specify a comma-separated list of servers in
#     {APP_PREFIX}_S3_ENGINES
#     and, for each engine, specify the set above, replacing 'S3' with
#     'AWS', 'ECS', and 'MINIO', respectively, for the engines listed

_S3_ACCESS_DATA: dict = {}
_S3_ENGINES: list[str] = []

_prefix: str = env_get_str(f"{APP_PREFIX}_S3_ENGINE",  None)
if _prefix:
    _default_setup: bool = True
    _S3_ENGINES.append(_prefix)
else:
    _default_setup: bool = False
    _engines: str = env_get_str(f"{APP_PREFIX}_S3_ENGINES", None)
    if _engines:
        _S3_ENGINES.extend(_engines.split(sep=","))
for engine in _S3_ENGINES:
    if _default_setup:
        _tag = "S3"
        _default_setup = False
    else:
        _tag: str = str_get_positional(source=engine,
                                       list_origin=["aws", "ecs", "minio"],
                                       list_dest=["AWS", "ECS", "MINIO"])
    _s3_data = {
        "endpoint-url": env_get_str(key=f"{APP_PREFIX}_{_tag}_ENDPOINT_URL"),
        "bucket-name": env_get_str(key=f"{APP_PREFIX}_{_tag}_BUCKET_NAME"),
        "access-key":  env_get_str(key=f"{APP_PREFIX}_{_tag}_ACCESS_KEY"),
        "secret-key": env_get_str(key=f"{APP_PREFIX}_{_tag}_SECRET_KEY"),
        "temp-folder": Path(env_get_str(key=f"{APP_PREFIX}_{_tag}_TEMP_FOLDER",
                                        def_value="/usr/tmp"))
    }
    if engine == "aws":
        _s3_data["region-name"] = env_get_str(f"{APP_PREFIX}_{_tag}_REGION_NAME")
    elif engine == "minio":
        _s3_data["secure-access"] = env_get_bool(f"{APP_PREFIX}_{_tag}_SECURE_ACCESS")
    _S3_ACCESS_DATA[engine] = _s3_data


def _assert_engine(errors: list[str],
                   engine: str) -> str:
    """
    Verify if *engine* is in the list of supported engines.

    If *engine* is a supported engine, it is returned. If its value is 'None',
    the first engine in the list of supported engines (the default engine) is returned.

    :param errors: incidental errors
    :param engine: the reference database engine
    :return: the validated or default engine
    """
    # initialize the return valiable
    result: str | None = None

    if not engine and _S3_ENGINES:
        result = _S3_ENGINES[0]
    elif engine in _S3_ENGINES:
        result = engine
    else:
        err_msg = f"S3 engine '{engine}' unknown or not configured"
        errors.append(err_msg)

    return result


def _get_param(engine: str,
               param: str) -> Any:
    """
    Return the current value of *param* being used by *engine*.

    :param engine: the reference S3 engine
    :param param: the reference parameter
    :return: the parameter's current value
    """
    return _S3_ACCESS_DATA[engine].get(param)


def _get_params(engine: str) -> tuple:
    """
    Return the current parameters being used for *engine*.

    The parameters are returned as a *tuple*, with the elements
    *endpoint-url*, *bucket-name*, *temp-folder*, *access-key*, and *secret-key*.
    For *aws* and *minio* engines, the extra elements *region-name* and
    *secure-access* are returned, respectively.
    The meaning of some parameters may vary between different S3 engines.

    :param engine: the reference database engine
    :return: the current parameters for the engine
    """
    endpoint_url: str = _S3_ACCESS_DATA[engine].get("endpoint-url")
    bucket_name: str = _S3_ACCESS_DATA[engine].get("bucket-name")
    temp_folder: str = _S3_ACCESS_DATA[engine].get("temp-folder")
    access_key: str = _S3_ACCESS_DATA[engine].get("access-key")
    secret_key: str = _S3_ACCESS_DATA[engine].get("secret-key")

    result: tuple | None = None
    if engine == "aws":
        region_name: str = _S3_ACCESS_DATA[engine].get("region-name")
        result = (endpoint_url, bucket_name, temp_folder,
                  access_key, secret_key, region_name)
    elif engine == "ecs":
        result = (endpoint_url, bucket_name, temp_folder,
                  access_key, secret_key)
    elif engine == "minio":
        secure_access: bool = _S3_ACCESS_DATA[engine].get("secure-access")
        result = (endpoint_url, bucket_name, temp_folder,
                  access_key, secret_key, secure_access)

    return result


def _except_msg(errors: list[str],
                exception: Exception,
                engine: str,
                logger: Logger) -> None:
    """
    Format and log the error message corresponding to the exception raised while accessing the S3 store.

    :param errors: incidental error messages
    :param exception: the exception raised
    :param logger: the logger object
    :param engine: the reference database engine
    :return: the formatted error message
    """
    endpoint: str = _S3_ACCESS_DATA[engine].get("endpoint-url")
    err_msg: str = f"Error accessing '{engine}' at '{endpoint}': {str_sanitize(f'{exception}')}"
    if isinstance(errors, list):
        errors.append(err_msg)
    if logger:
        logger.error(err_msg)


def _log(logger: Logger,
         err_msg: str = None,
         level: int = DEBUG,
         errors: list[str] = None,
         stmt: str = None) -> None:
    """
    Log *err_msg* and add it to *errors*, or else log *stmt*, whichever is applicable.

    :param logger: the logger object
    :param err_msg: the error message to log
    :param level: log level (defaults to DEBUG)
    :param errors: optional incidental errors
    :param stmt: optional statement
    """
    if err_msg:
        if logger:
            logger.log(level, err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)
    if logger and stmt:
        logger.log(level, stmt)
