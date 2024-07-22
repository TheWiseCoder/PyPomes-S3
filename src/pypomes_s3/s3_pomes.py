from collections.abc import Iterator
from logging import Logger
from pathlib import Path
from pypomes_http import MIMETYPE_BINARY
from typing import Any, Literal, BinaryIO

from .s3_common import (
    _S3_ENGINES, _S3_ACCESS_DATA,
    _assert_engine, _get_param
)


def s3_setup(engine: Literal["aws", "ecs", "minio"],
             endpoint_url: str,
             bucket_name: str,
             access_key: str,
             secret_key: str,
             region_name: str = None,
             secure_access: bool = None) -> bool:
    """
    Establish the provided parameters for access to *engine*.

    The meaning of some parameters may vary between different S3 engines.
    All parameters, are required, with these exceptions:
        - *region_name* is required for *aws*, only
        - *secure_access* may be provided for *minio*, only

    :param engine: the S3 engine (one of ['aws', 'ecs', 'minio'])
    :param endpoint_url: the access URL for the service
    :param bucket_name: the name of the default bucket
    :param access_key: the access key for the service
    :param secret_key: the access secret code
    :param region_name: the name of the region where the engine is located (AWS only)
    :param secure_access: whether or not to use Transport Security Layer (MinIO only)
    :return: 'True' if the data was accepted, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # are the parameters compliant ?
    if (engine in ["aws", "ecs", "minio"] and
        endpoint_url and bucket_name and access_key and secret_key and
        not (engine != "aws" and region_name) and
        not (engine == "aws" and not region_name) and
        not (engine != "minio" and secure_access is not None) and
        not (engine == "minio" and secure_access is None)):
        _S3_ACCESS_DATA[engine] = {
            "endpoint-url": endpoint_url,
            "bucket-name": bucket_name,
            "access-key": access_key,
            "secret-key": secret_key
        }
        if engine == "aws":
            _S3_ACCESS_DATA[engine]["region-name"] = region_name
        elif engine == "minio":
            _S3_ACCESS_DATA[engine]["secure-access"] = secure_access
        if engine not in _S3_ENGINES:
            _S3_ENGINES.append(engine)
        result = True

    return result


def s3_get_engines() -> list[str]:
    """
    Retrieve and return the list of configured engines.

    This list may include any of the supported engines: *aws*, *ecs*, *minio*.

    :return: the list of configured engines
    """
    # SANITY-CHECK: return a cloned 'list'
    return _S3_ENGINES.copy()


def s3_get_param(key: Literal["endpoint-url", "bucket-name",
                              "access-key", "secret-key", "region-name", "secure-access"],
                 engine: str = None) -> str:
    """
    Return the connection parameter value for *key*.

    The connection key should be one of *endpoint-url*, *bucket-name", *access-key*, and *secret-key*.
    For *aws* and *minio* engines, the extra keys *region-name* and *secure-access* are added to this list,
    respectively.

    :param key: the reference parameter
    :param engine: the reference S3 engine (the default engine, if not provided)
    :return: the current value of the connection parameter
    """
    # determine the S3 engine
    curr_engine: str = _S3_ENGINES[0] if not engine and _S3_ENGINES else engine

    return _get_param(curr_engine, key)


def s3_get_params(engine: str = None) -> dict[str, Any]:
    """
    Return the access parameters as a *dict*.

    The returned *dict* contains the keys *endpoint-url*, *bucket-name*, and *access-key*,
    and the extra keys *region-name* and *secure-access*, for *aws* and *minio* engines, respectively.
    The meaning of these parameters may vary between different S3 engines.

    :param engine: the database engine
    :return: the current connection parameters for the engine
    """
    curr_engine: str = _S3_ENGINES[0] if not engine and _S3_ENGINES else engine

    # SANITY-CHECK: return a cloned 'dict'
    return dict(_S3_ACCESS_DATA.get(curr_engine))


def s3_assert_access(errors: list[str] | None,
                     engine: str = None,
                     logger: Logger = None) -> bool:
    """
    Determine whether the *engine*'s current configuration allows for accessing the S3 services.

    :param errors: incidental errors
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param logger: optional logger
    :return: 'True' if accessing succeeded, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # make sure to have a S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    if curr_engine:
        client: Any = s3_get_client(errors=op_errors,
                                    engine=curr_engine,
                                    logger=logger)
        result = client is not None

    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_startup(errors: list[str] | None,
               engine: str = None,
               bucket: str = None,
               logger: Logger = None) -> bool:
    """
    Prepare the S3 client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the S3 service is fully functional.

    :param errors: incidental error messages
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use
    :param logger: optional logger
    :return: 'True' if service is fully functional
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.startup(errors=op_errors,
                                   bucket=bucket,
                                   logger=logger)
    if curr_engine == "ecs":
        pass
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.startup(errors=op_errors,
                                     bucket=bucket,
                                     logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_get_client(errors: list[str] | None,
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
        result = aws_pomes.get_client(errors=op_errors,
                                      logger=logger)
    if curr_engine == "ecs":
        pass
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.get_client(errors=op_errors,
                                        logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_data_store(errors: list[str],
                  basepath: str | Path,
                  identifier: str,
                  data: bytes | str | BinaryIO,
                  length: int = -1,
                  mimetype: str = MIMETYPE_BINARY,
                  tags: dict = None,
                  bucket: str = None,
                  engine: Any = None,
                  client: Any = None,
                  logger: Logger = None) -> bool:
    """
    Store data at the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the data at
    :param identifier: the data identifier
    :param data: the data to store
    :param length: the length of the data (defaults to -1: unknown)
    :param mimetype: the data mimetype
    :param tags: optional metadata describing the data
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if the data was successfully stored, False otherwise
    """
    # initialize the return variable
    result: bool | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.file_store(errors=op_errors,
                                      bucket=bucket,
                                      basepath=basepath,
                                      identifier=identifier,
                                      filepath="",
                                      mimetype=mimetype,
                                      tags=tags,
                                      client=client,
                                      logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.data_store(errors=op_errors,
                                        bucket=bucket,
                                        basepath=basepath,
                                        identifier=identifier,
                                        data=data,
                                        length=length,
                                        mimetype=mimetype,
                                        tags=tags,
                                        client=client,
                                        logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_data_retrieve(errors: list[str],
                     basepath: str | Path,
                     identifier: str,
                     offset: int = 0,
                     length: int = 0,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> bytes:
    """
    Retrieve data from the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the data from
    :param identifier: the data identifier
    :param offset: the start position within the data (in bytes, defaults to 0: data start)
    :param length: the length of the data to retrieve (in bytes, defaults to 0: to data finish)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the bytes retrieved, or 'None' if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.file_retrieve(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         filepath="",
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.data_retrieve(errors=op_errors,
                                           bucket=bucket,
                                           basepath=basepath,
                                           identifier=identifier,
                                           offset=offset,
                                           length=length,
                                           client=client,
                                           logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_file_store(errors: list[str],
                  basepath: str | Path,
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
    :return: 'True' if the file was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
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
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_file_retrieve(errors: list[str],
                     basepath: str | Path,
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
    :return: information about the file retrieved, or 'None' if error or file not found
    """
    # initialize the return variable
    result: Any = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
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
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_object_store(errors: list[str],
                    basepath: str | Path,
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
    :return: 'True' if the object was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
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
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_object_retrieve(errors: list[str],
                       basepath: str | Path,
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
    :return: the object retrieved, or 'None' if error or object not found
    """
    # initialize the return variable
    result: Any = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
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
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_item_exists(errors: list[str],
                   basepath: str | Path,
                   identifier: str | None,
                   bucket: str = None,
                   engine: str = None,
                   client: Any = None,
                   logger: Logger = None) -> bool:
    """
    Determine if a given item exists in the S3 store.
    
    The item might be unspecified data, a file, or an object.

    :param errors: incidental error messages
    :param basepath: the path specifying where to locate the item
    :param identifier: optional item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the item was found, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.item_exists(errors=op_errors,
                                       bucket=bucket,
                                       basepath=basepath,
                                       identifier=identifier,
                                       client=client,
                                       logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.item_exists(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_item_stat(errors: list[str],
                 basepath: str | Path,
                 identifier: str,
                 bucket: str = None,
                 engine: str = None,
                 client: Any = None,
                 logger: Logger = None) -> Any:
    """
    Retrieve and return the information about an item in the S3 store.
    
    The item might be unspecified data, a file, or an object.

    :param errors: incidental error messages
    :param basepath: the path specifying where to locate the item
    :param identifier: the item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: metadata and information about the item, or 'None' if error or item not found
    """
    # initialize the return variable
    result: Any | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.item_stat(errors=op_errors,
                                     bucket=bucket,
                                     basepath=basepath,
                                     identifier=identifier,
                                     client=client,
                                     logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.item_stat(errors=op_errors,
                                       bucket=bucket,
                                       basepath=basepath,
                                       identifier=identifier,
                                       client=client,
                                       logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_item_remove(errors: list[str],
                   basepath: str | Path,
                   identifier: str = None,
                   bucket: str = None,
                   engine: str = None,
                   client: Any = None,
                   logger: Logger = None) -> bool:
    """
    Remove an item from the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the item from
    :param identifier: optional item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the item was successfully removed, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.item_remove(errors=op_errors,
                                       bucket=bucket,
                                       basepath=basepath,
                                       identifier=identifier,
                                       client=client,
                                       logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.item_remove(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_items_list(errors: list[str],
                  basepath: str | Path,
                  recursive: bool = False,
                  bucket: str = None,
                  engine: str = None,
                  client: Any = None,
                  logger: Logger = None) -> Iterator:
    """
    Retrieve and return an iterator into the list of items at *basepath*, in the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to iterate from
    :param recursive: whether the location is iterated recursively
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the iterator into the list of items, or 'None' if error or the path not found
    """
    # initialize the return variable
    result: Iterator | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.items_list(errors=op_errors,
                                      bucket=bucket,
                                      basepath=basepath,
                                      recursive=recursive,
                                      client=client,
                                      logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.items_list(errors=op_errors,
                                        bucket=bucket,
                                        basepath=basepath,
                                        recursive=recursive,
                                        client=client,
                                        logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_tags_retrieve(errors: list[str],
                     basepath: str | Path,
                     identifier: str,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> dict:
    """
    Retrieve and return the metadata information for an item in the S3 store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the item from
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata about the item, or 'None' if error or item not found
    """
    # initialize the return variable
    result: dict | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # determine the S3 engine
    curr_engine: str = _assert_engine(errors=op_errors,
                                      engine=engine)
    # make sure to have a bucket
    bucket = bucket or _get_param(engine=curr_engine,
                                  param="bucket-name")
    if curr_engine == "aws":
        from . import aws_pomes
        result = aws_pomes.tags_retrieve(errors=op_errors,
                                         bucket=bucket,
                                         basepath=basepath,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.tags_retrieve(errors=op_errors,
                                           bucket=bucket,
                                           basepath=basepath,
                                           identifier=identifier,
                                           client=client,
                                           logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result
