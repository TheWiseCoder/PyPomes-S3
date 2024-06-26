from collections.abc import Iterator
from logging import Logger
from pathlib import Path
from typing import Any

from .s3_common import (
    _S3_ENGINES, _S3_ACCESS_DATA,
    _assert_engine, _s3_get_param
)


def s3_setup(engine: str,
             access_key: str,
             access_secret: str,
             bucket_name: str,
             temp_folder: str | Path,
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
    :param temp_folder: path for temporary files
    :param region_name: the name of the region where the engine is located (AWS only)
    :param endpoint_url: the access URL for the service (MinIO only)
    :param secure_access: whether or not to use Transport Security Layer (MinIO only)
    :return: True if the data was accepted, False otherwise
    """
    # initialize the return variable
    result: bool = False

    # are the parameters compliant ?
    if (engine in ["aws", "minio"] and
        access_key and access_secret and bucket_name and temp_folder and
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
            "temp-folder": temp_folder
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


def s3_get_params(engine: str = None) -> dict:
    """
    Return the access parameters as a *dict*.

    The returned *dict* contains the keys *name*, *user*, *pwd*, *host*, *port*.
    The meaning of these parameters may vary between different database engines.

    :param engine: the database engine
    :return: the current connection parameters for the engine
    """
    curr_engine: str = _S3_ENGINES[0] if not engine and _S3_ENGINES else engine
    return _S3_ACCESS_DATA.get(engine or curr_engine)


def s3_assert_access(errors: list[str] | None,
                     engine: str = None,
                     logger: Logger = None) -> bool:
    """
    Determine whether the *engine*'s current configuration allows for accessing the S3 services.

    :param errors: incidental errors
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param logger: optional logger
    :return: True if the accessing succeeded, False otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # make sure to have a S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)

    if curr_engine:
        client: Any = s3_access(errors=op_errors,
                                engine=curr_engine,
                                logger=logger)
        result = client is not None

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_access(errors: list[str] | None,
              engine: str = None,
              logger: Logger = None) -> Any:
    """
    Obtain and return a client to *engine*, or *None* if the client cannot be obtained.

    The target S3 engine, default or specified, must have been previously configured.

    :param errors: incidental error messages
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param logger: optional logger
    :return: the client to the S3 engine
    """
    # initialize the return variable
    result: Any = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.access(errors=op_errors,
                                  logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.access(errors=op_errors,
                                    logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_startup(errors: list[str],
               bucket: str = None,
               engine: str = None,
               logger: Logger = None) -> bool:
    """
    Prepare the S3 *client* for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the MinIo service is fully functional.

    :param errors: incidental error messages
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param logger: optional logger
    :return: True if service is fully functional
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.startup(errors=op_errors,
                                   bucket=bucket,
                                   logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.startup(errors=op_errors,
                                     bucket=bucket,
                                     logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_file_store(errors: list[str],
                  basepath: str,
                  identifier: str,
                  filepath: Path | str,
                  mimetype: str,
                  tags: dict = None,
                  bucket: str = None,
                  engine: Any = None,
                  client: Any = None,
                  logger: Logger = None) -> bool:
    """
    Store a file at the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the file at
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata describing the file
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if the file was successfully stored, False otherwise
    """
    # initialize the return variable
    result: bool | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.file_store(errors=op_errors,
                                      bucket=bucket,
                                      basepath=basepath,
                                      identifier=identifier,
                                      filepath=filepath,
                                      mimetype=mimetype,
                                      tags=tags,
                                      client=client,
                                      logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.file_store(errors=op_errors,
                                        bucket=bucket,
                                        basepath=basepath,
                                        identifier=identifier,
                                        filepath=filepath,
                                        mimetype=mimetype,
                                        tags=tags,
                                        client=client,
                                        logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_file_retrieve(errors: list[str],
                     basepath: str,
                     identifier: str,
                     filepath: Path | str,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> Any:
    """
    Retrieve a file from the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the file from
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information about the file retrieved
    """
    # initialize the return variable
    result: Any = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.file_retrieve(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         filepath=filepath,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.file_retrieve(errors=op_errors,
                                           bucket=bucket,
                                           basepath=basepath,
                                           identifier=identifier,
                                           filepath=filepath,
                                           client=client,
                                           logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_object_exists(errors: list[str],
                     basepath: str,
                     identifier: str | None,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> bool:
    """
    Determine if a given object exists in the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying where to locate the object
    :param identifier: optional object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if the object was found, false otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.object_exists(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.object_exists(errors=op_errors,
                                           bucket=bucket,
                                           basepath=basepath,
                                           identifier=identifier,
                                           client=client,
                                           logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_object_stat(errors: list[str],
                   basepath: str,
                   identifier: str,
                   bucket: str = None,
                   engine: str = None,
                   client: Any = None,
                   logger: Logger = None) -> Any:
    """
    Retrieve and return the information about an object in the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying where to locate the object
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: metadata and information about the object
    """
    # initialize the return variable
    result: Any | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.object_stat(errors=op_errors,
                                       bucket=bucket,
                                       basepath=basepath,
                                       identifier=identifier,
                                       client=client,
                                       logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.object_stat(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_object_store(errors: list[str],
                    basepath: str,
                    identifier: str,
                    obj: Any,
                    tags: dict = None,
                    bucket: str = None,
                    engine: str = None,
                    client: Any = None,
                    logger: Logger = None) -> bool:
    """
    Store an object at the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the object at
    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadata describing the object
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if the object was successfully stored, False otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.object_store(errors=op_errors,
                                        bucket=bucket,
                                        basepath=basepath,
                                        identifier=identifier,
                                        obj=obj,
                                        tags=tags,
                                        client=client,
                                        logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.object_store(errors=op_errors,
                                          bucket=bucket,
                                          basepath=basepath,
                                          identifier=identifier,
                                          obj=obj,
                                          tags=tags,
                                          client=client,
                                          logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_object_retrieve(errors: list[str],
                       basepath: str,
                       identifier: str,
                       bucket: str = None,
                       engine: str = None,
                       client: Any = None,
                       logger: Logger = None) -> Any:
    """
    Retrieve an object from the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the object retrieved
    """
    # initialize the return variable
    result: Any = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.object_retrieve(errors=op_errors,
                                           bucket=bucket,
                                           basepath=basepath,
                                           identifier=identifier,
                                           client=client,
                                           logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.object_retrieve(errors=op_errors,
                                             bucket=bucket,
                                             basepath=basepath,
                                             identifier=identifier,
                                             client=client,
                                             logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_object_delete(errors: list[str],
                     basepath: str,
                     identifier: str = None,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> bool:
    """
    Remove an object from the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: optional object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if the object was successfully deleted, False otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.object_delete(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.object_delete(errors=op_errors,
                                           bucket=bucket,
                                           basepath=basepath,
                                           identifier=identifier,
                                           client=client,
                                           logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_object_tags_retrieve(errors: list[str],
                            basepath: str,
                            identifier: str,
                            bucket: str = None,
                            engine: str = None,
                            client: Any = None,
                            logger: Logger = None) -> dict:
    """
    Retrieve and return the metadata information for an object in the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata about the object
    """
    # initialize the return variable
    result: dict | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.object_tags_retrieve(errors=op_errors,
                                                bucket=bucket,
                                                basepath=basepath,
                                                identifier=identifier,
                                                client=client,
                                                logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.object_tags_retrieve(errors=op_errors,
                                                  bucket=bucket,
                                                  basepath=basepath,
                                                  identifier=identifier,
                                                  client=client,
                                                  logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result


def s3_objects_list(errors: list[str],
                    basepath: str,
                    recursive: bool = False,
                    bucket: str = None,
                    engine: str = None,
                    client: Any = None,
                    logger: Logger = None) -> Iterator:
    """
    Retrieve and return an iterator into the list of objects at *basepath*, in the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to iterate from
    :param recursive: whether the location is iterated recursively
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the iterator into the list of objects, 'None' if the folder does not exist
    """
    # initialize the return variable
    result: Iterator | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket name
    if not bucket:
        bucket = _s3_get_param(engine=curr_engine,
                               param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.objects_list(errors=op_errors,
                                        bucket=bucket,
                                        basepath=basepath,
                                        recursive=recursive,
                                        client=client,
                                        logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.objects_list(errors=op_errors,
                                          bucket=bucket,
                                          basepath=basepath,
                                          recursive=recursive,
                                          client=client,
                                          logger=logger)

    # acknowledge eventual local errors
    errors.extend(op_errors)

    return result
