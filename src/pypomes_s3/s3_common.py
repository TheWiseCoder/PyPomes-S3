from pypomes_core import (
    APP_PREFIX,
    env_get_bool, env_get_str, env_get_strs, str_sanitize
)
from enum import StrEnum, auto
from typing import Any
from unidecode import unidecode


class S3Engine(StrEnum):
    """
    Supported S3 engines.
    """
    AWS = auto()
    MINIO = auto()


class S3Param(StrEnum):
    """
    Parameters for connecting to S3 engines.
    """
    ENGINE = "engine"
    ENDPOINT_URL = "endpoint-url"
    BUCKET_NAME = "bucket-name"
    ACCESS_KEY = "access-key"
    SECRET_KEY = "secret-key"
    SECURE_ACCESS = "secure-access"
    REGION_NAME = "region-name"


# - the preferred way to specify S3 storage parameters is dynamically with 's3_setup_params'
# - specifying S3 storage parameters with environment variables can be done in two ways:
#   1. specify the set
#     {APP_PREFIX}_S3_ENGINE (one of 'aws', 'minio')
#     {APP_PREFIX}_S3_ENDPOINT_URL
#     {APP_PREFIX}_S3_BUCKET_NAME
#     {APP_PREFIX}_S3_ACCESS_KEY
#     {APP_PREFIX}_S3_SECRET_KEY
#     {APP_PREFIX}_S3_SECURE_ACCESS
#     {APP_PREFIX}_S3_REGION_NAME
#   2. alternatively, specify a comma-separated list of servers in
#     {APP_PREFIX}_S3_ENGINES
#     and, for each engine, specify the set above, replacing 'S3' with
#     'AWS' and 'MINIO', respectively, for the engines listed

_S3_ACCESS_DATA: dict[S3Engine, dict[S3Param, Any]] = {}
_S3_ENGINES: list[S3Engine] = []

_engine: str = env_get_str(key=f"{APP_PREFIX}_S3_ENGINE",
                           values=list(map(str, S3Engine)))
if _engine:
    _default_setup: bool = True
    _S3_ENGINES.append(S3Engine(_engine))
else:
    _default_setup: bool = False
    _engines: list[str] = env_get_strs(key=f"{APP_PREFIX}_S3_ENGINES",
                                       values=list(map(str, S3Engine)))
    if _engines:
        _S3_ENGINES.extend([S3Engine(v) for v in _engines])
for _s3_engine in _S3_ENGINES:
    if _default_setup:
        _tag = "S3"
        _default_setup = False
    else:
        _tag = _s3_engine.upper()
    _S3_ACCESS_DATA[_s3_engine] = {
        S3Param.ENDPOINT_URL: env_get_str(key=f"{APP_PREFIX}_{_tag}_ENDPOINT_URL"),
        S3Param.BUCKET_NAME: env_get_str(key=f"{APP_PREFIX}_{_tag}_BUCKET_NAME"),
        S3Param.ACCESS_KEY:  env_get_str(key=f"{APP_PREFIX}_{_tag}_ACCESS_KEY"),
        S3Param.SECRET_KEY: env_get_str(key=f"{APP_PREFIX}_{_tag}_SECRET_KEY"),
        S3Param.SECURE_ACCESS: env_get_bool(key=f"{APP_PREFIX}_{_tag}_SECURE_ACCESS"),
        S3Param.REGION_NAME: env_get_str(key=f"{APP_PREFIX}_{_tag}_REGION_NAME")
    }


def _assert_engine(errors: list[str],
                   engine: S3Engine) -> S3Engine:
    """
    Verify if *engine* is in the list of supported engines.

    If *engine* is a supported engine, it is returned. If its value is *None*,
    the first engine in the list of supported engines (the default engine) is returned.

    :param errors: incidental errors
    :param engine: the reference database engine
    :return: the validated or the default engine
    """
    # initialize the return valiable
    result: S3Engine | None = None

    if not engine and _S3_ENGINES:
        result = _S3_ENGINES[0]
    elif engine in _S3_ENGINES:
        result = engine
    else:
        err_msg = f"S3 engine '{engine}' unknown or not configured"
        errors.append(err_msg)

    return result


def _get_param(engine: S3Engine,
               param: S3Param) -> Any:
    """
    Return the current value of *param* being used by *engine*.

    :param engine: the reference S3 engine
    :param param: the reference parameter
    :return: the parameter's current value
    """
    return (_S3_ACCESS_DATA.get(engine) or {}).get(param)


def _get_params(engine: S3Engine) -> dict[S3Param, Any]:
    """
    Return the current parameters being used for *engine*.

    :param engine: the reference database engine
    :return: the current parameters for the engine
    """
    return _S3_ACCESS_DATA.get(engine)


def _except_msg(exception: Exception,
                engine: S3Engine) -> str:
    """
    Format and return the error message corresponding to the exception raised while accessing the S3 store.

    :param exception: the exception raised
    :param engine: the reference database engine
    :return: the formatted error message
    """
    endpoint: str = (_S3_ACCESS_DATA.get(engine) or {}).get(S3Param.ENDPOINT_URL)
    return f"Error accessing '{engine}' at '{endpoint}': {str_sanitize(source=f'{exception}')}"


def _normalize_tags(tags: dict[str, str]) -> dict[str, str]:

    # initialize the return variable
    result: dict[str, str] | None = None

    # have tags been defined ?
    if tags:
        # yes, process them
        result = {}
        for key, value in tags.items():
            # normalize 'key' and 'value', by removing all diacritics
            result[unidecode(string=key).lower()] = unidecode(string=value)

    return result
