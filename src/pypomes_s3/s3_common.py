from pypomes_core import (
    APP_PREFIX,
    env_get_bool, env_get_str, env_get_strs,
    env_get_enum, str_sanitize, obj_positional
)
from enum import StrEnum, auto
from logging import Logger
from typing import Any, Final
from unidecode import unidecode


class S3Engine(StrEnum):
    """
    Supported S3 engines.
    """
    AWS = auto()
    GCS = auto()
    MINIO = auto()


class S3Param(StrEnum):
    """
    Parameters for connecting to S3 engines.
    """
    # all engines
    ENGINE_ID = "engine-id"
    ENGINE_TYPE = "engine-type"
    BUCKET_NAME = "bucket-name"
    VERSION = "version"

    # AWS and MinIO
    ENDPOINT_URL = "endpoint-url"
    ACCESS_KEY = "access-key"
    SECRET_KEY = "secret-key"
    SECURE_ACCESS = "secure-access"
    REGION_NAME = "region-name"

    # GCS
    CREDENTIALS = "credentials"
    PROJECT_ID = "project-id"


# S3 loggers
_S3_LOGGERS: Final[dict[str, Logger | None]] = {}


def __get_access_data() -> dict[str, dict[S3Param, Any]]:
    """
    Establish the access data for select S3 engines, from environment variables.

    Sepcifying S3 storage parameters dynamically with 'gcs_setup()' is the required way for GCS engines,
    if authentication is done through credential key/value pairs, whereas specifying S3 storage parameters
    dynamically with 's3_setup()' is the preferred way for AWS and MinIO engines. Specifying S3 storage
    parameters with environment variables can be done in two ways:
      - 1. for a single S3 engine, specify the set
           - *<APP_PREFIX>_S3_ENGINE_ID*
           - *<APP_PREFIX>_S3_ENGINE_TYPE* (one of *aws*, *minio*, *gcs*)
           - *<APP_PREFIX>_S3_BUCKET_NAME*
           - *<APP_PREFIX>_S3_CREDENTIALS* (GCS)
           - *<APP_PREFIX>_S3_PROJECT_ID* (GCS)
           - *<APP_PREFIX>_S3_ENDPOINT_URL* (AWS, MinIO)
           - *<APP_PREFIX>_S3_ACCESS_KEY* (AWS, MinIO)
           - *<APP_PREFIX>_S3_SECRET_KEY* (AWS, MinIO)
           - *<APP_PREFIX>_S3_SECURE_ACCESS* (AWS, MinIO)
           - *<APP_PREFIX>_S3_REGION_NAME* (AWS, MinIO)
      - 2. for multiple S3 engines, specify a comma-separated list of engines in
           *<APP_PREFIX>_S3_ENGINES, and, for each engine, specify the set above, respectively replacing
           *_S3_* with *_AWS_*, *_MINIO_*, and *_GCS_*, for the engines listed

    :return: the access data for the selected S3 engines
    """
    # initialize the return variable
    result: dict[str, dict[S3Param, Any]] = {}

    engines: list[str] = []
    single_engine: str = env_get_str(key=f"{APP_PREFIX}_S3_ENGINE_ID")
    if single_engine:
        default_setup: bool = True
        engines.append(single_engine)
    else:
        default_setup: bool = False
        multi_engines: list[str] = env_get_strs(key=f"{APP_PREFIX}_S3_ENGINES")
        if multi_engines:
            engines.extend(multi_engines)

    for engine in engines:
        if default_setup:
            prefix: str = "S3"
            default_setup = False
        else:
            prefix: str = engine
        s3_type: S3Engine = env_get_enum(key=f"{APP_PREFIX}_{prefix}_ENGINE_TYPE",
                                         enum_class=S3Engine,
                                         values=[S3Engine.AWS, S3Engine.MINIO])
        if not s3_type:
            s3_type = obj_positional(engine,
                                     keys=("AWS", "MINIO"),
                                     values=(S3Engine.AWS, S3Engine.MINIO))
        if not s3_type:
            raise ValueError(f"Unable to establish type for S3 engine '{engine}'")
        result[engine] = {
            S3Param.BUCKET_NAME: env_get_str(key=f"{APP_PREFIX}_{prefix}_BUCKET_NAME"),
            S3Param.ENGINE_TYPE: s3_type,
            S3Param.VERSION: ""
        }
        if s3_type in [S3Engine.AWS, S3Engine.MINIO]:
            result[engine].update({
                S3Param.ENDPOINT_URL: env_get_str(key=f"{APP_PREFIX}_{prefix}_ENDPOINT_URL"),
                S3Param.BUCKET_NAME: env_get_str(key=f"{APP_PREFIX}_{prefix}_BUCKET_NAME"),
                S3Param.ACCESS_KEY: env_get_str(key=f"{APP_PREFIX}_{prefix}_ACCESS_KEY"),
                S3Param.SECRET_KEY: env_get_str(key=f"{APP_PREFIX}_{prefix}_SECRET_KEY"),
                S3Param.REGION_NAME: env_get_str(key=f"{APP_PREFIX}_{prefix}_REGION_NAME")
            })
            if s3_type == S3Engine.MINIO:
                result[engine][S3Param.SECURE_ACCESS] = env_get_bool(key=f"{APP_PREFIX}_{prefix}_SECURE_ACCESS")
        elif s3_type == S3Engine.GCS:
            result[engine][S3Param.PROJECT_ID] = env_get_str(key=f"{APP_PREFIX}_{prefix}_PROJECT_ID")
        _S3_LOGGERS[engine] = None

    return result


# access data for the configured S3 engines
_S3_ACCESS_DATA: Final[dict[str, dict[S3Param, Any]]] = __get_access_data()


def _assert_engine(engine: S3Engine | str,
                   errors: list[str] = None) -> tuple[str, S3Engine]:
    """
    Verify if *engine* is in the list of supported engines.

    If *engine* is a supported engine, it is returned. If its value is *None*,
    the first engine in the list of supported engines (the default engine) is returned.

    :param engine: the reference database engine
    :param errors: incidental errors
    :return: the validated or the default engine
    """
    # initialize the return valiable
    result: tuple[str | None, S3Engine | None] | None = None

    for key, value in _S3_ACCESS_DATA.items():
        if not engine or engine == key:
            result = (key, value.get(S3Param.ENGINE_TYPE))
            break
    if not result:
        for key, value in _S3_ACCESS_DATA.items():
            if engine == value.get(S3Param.ENGINE_TYPE):
                result = (key, value[S3Param.ENGINE_TYPE])
                break

    if not result:
        if isinstance(errors, list):
            errors.append(f"S3 engine '{engine}' unknown or not configured")
        result = (None, None)

    return result


def _get_param(engine_id: str,
               param: S3Param) -> Any:
    """
    Return the current value of *param* being used by *engine*.

    :param engine_id: the reference S3 engine
    :param param: the reference parameter
    :return: the parameter's current value
    """
    return (_S3_ACCESS_DATA.get(engine_id) or {}).get(param)


def _get_params(engine_id: str) -> dict[S3Param, Any]:
    """
    Return the current parameters being used for *engine*.

    :param engine_id: the reference database engine
    :return: the current parameters for the engine
    """
    return _S3_ACCESS_DATA.get(engine_id)


def _except_msg(exception: Exception,
                engine_id: str) -> str:
    """
    Format and return the error message corresponding to the exception raised while accessing the S3 store.

    :param exception: the exception raised
    :param engine_id: the reference database engine
    :return: the formatted error message
    """
    endpoint: str = (_S3_ACCESS_DATA.get(engine_id) or {}).get(S3Param.ENDPOINT_URL)
    return f"Error accessing '{engine_id}' at '{endpoint}': {str_sanitize(f'{exception}')}"


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
