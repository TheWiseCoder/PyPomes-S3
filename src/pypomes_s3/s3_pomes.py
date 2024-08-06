import pickle
from logging import Logger
from pathlib import Path
from typing import Any, Literal, BinaryIO

from .s3_common import (
    MIMETYPE_BINARY, _S3_ENGINES, _S3_ACCESS_DATA,
    _assert_engine, _get_param, _except_msg
)


def s3_setup(engine: Literal["aws", "minio"],
             endpoint_url: str,
             bucket_name: str,
             access_key: str,
             secret_key: str,
             region_name: str = None,
             secure_access: bool = None) -> bool:
    """
    Establish the provided parameters for access to *engine*.

    The meaning of some parameters may vary between different S3 engines.
    All parameters, with the exception of *region_name* and *secure_access*, are required.

    :param engine: the S3 engine (one of ['aws', 'minio'])
    :param endpoint_url: the access URL for the service
    :param bucket_name: the name of the default bucket
    :param access_key: the access key for the service
    :param secret_key: the access secret code
    :param region_name: the name of the region where the engine is located
    :param secure_access: whether or not to use Transport Security Layer
    :return: 'True' if the data was accepted, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # process te parameters
    if engine in ["aws", "minio"] and \
       endpoint_url and bucket_name and \
       access_key and secret_key:
        _S3_ACCESS_DATA[engine] = {
            "endpoint-url": endpoint_url,
            "bucket-name": bucket_name,
            "access-key": access_key,
            "secret-key": secret_key,
            "secure-access": secure_access,
            "region-name": region_name
        }
        if engine not in _S3_ENGINES:
            _S3_ENGINES.append(engine)
        result = True

    return result


def s3_get_engines() -> list[str]:
    """
    Retrieve and return the list of configured engines.

    This list may include any of the supported engines: *aws*, *minio*.

    :return: the list of configured engines
    """
    # SANITY-CHECK: return a cloned 'list'
    return _S3_ENGINES.copy()


def s3_get_param(key: Literal["endpoint-url", "bucket-name", "access-key",
                              "secret-key", "region-name", "secure-access"],
                 engine: str = None) -> str:
    """
    Return the connection parameter value for *key*.

    The connection key should be one of *endpoint-url*, *bucket-name", *access-key*, and *secret-key*.
    For *aws* and *minio* engines, the extra keys *region-name* and *secure-access* are added to this list,
    respectively.

    :param key: the connection parameter
    :param engine: the reference S3 engine (the default engine, if not provided)
    :return: the current value of the connection parameter
    """
    # determine the S3 engine
    curr_engine: str = _S3_ENGINES[0] if not engine and _S3_ENGINES else engine

    return _get_param(engine=curr_engine,
                      param=key)


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
    return s3_get_client(errors=errors,
                         engine=engine,
                         logger=logger) is not None


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
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.get_client(errors=op_errors,
                                        logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_data_retrieve(errors: list[str],
                     prefix: str | Path,
                     identifier: str,
                     data_range: tuple[int, int] = None,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> bytes:
    """
    Retrieve data from the S3 store.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to retrieve the data from
    :param identifier: the data identifier
    :param data_range: the begin-end positions within the data (in bytes, defaults to 'None' - all bytes)
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
        result = aws_pomes.data_retrieve(errors=op_errors,
                                         bucket=bucket,
                                         prefix=prefix,
                                         identifier=identifier,
                                         data_range=data_range,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.data_retrieve(errors=op_errors,
                                           bucket=bucket,
                                           prefix=prefix,
                                           identifier=identifier,
                                           data_range=data_range,
                                           client=client,
                                           logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_data_store(errors: list[str],
                  prefix: str | Path,
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
    :param prefix: the path specifying the location to store the data at
    :param identifier: the data identifier
    :param data: the data to store
    :param length: the length of the data (MinIO only, defaults to -1: unknown)
    :param mimetype: the data mimetype
    :param tags: optional metadata tags describing the data
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
        result = aws_pomes.data_store(errors=op_errors,
                                      bucket=bucket,
                                      prefix=prefix,
                                      identifier=identifier,
                                      data=data,
                                      mimetype=mimetype,
                                      tags=tags,
                                      client=client,
                                      logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.data_store(errors=op_errors,
                                        bucket=bucket,
                                        prefix=prefix,
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


def s3_file_retrieve(errors: list[str],
                     prefix: str | Path,
                     identifier: str,
                     filepath: Path | str,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> Any:
    """
    Retrieve a file from the S3 store.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to retrieve the file from
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
                                         prefix=prefix,
                                         identifier=identifier,
                                         filepath=filepath,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.file_retrieve(errors=op_errors,
                                           bucket=bucket,
                                           prefix=prefix,
                                           identifier=identifier,
                                           filepath=filepath,
                                           client=client,
                                           logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_file_store(errors: list[str],
                  prefix: str | Path,
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
    :param prefix: the path specifying the location to store the file at
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadatatagsdescribing the file
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
                                      prefix=prefix,
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
                                        prefix=prefix,
                                        identifier=identifier,
                                        filepath=filepath,
                                        mimetype=mimetype,
                                        tags=tags,
                                        client=client,
                                        logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_object_retrieve(errors: list[str],
                       prefix: str | Path,
                       identifier: str,
                       bucket: str = None,
                       engine: str = None,
                       client: Any = None,
                       logger: Logger = None) -> Any:
    """
    Retrieve an object from the S3 store.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the object retrieved, or 'None' if error or object not found
    """
    # initialize the return variable
    result: Any = None

    # retrieve the data
    data: bytes = s3_data_retrieve(errors=errors,
                                   prefix=prefix,
                                   identifier=identifier,
                                   bucket=bucket,
                                   engine=engine,
                                   client=client,
                                   logger=logger)
    # was the data obtained ?
    if data:
        # yes, umarshall the corresponding object
        try:
            result = pickle.loads(data)
        except Exception as e:
            _except_msg(errors=errors,
                        exception=e,
                        engine="minio",
                        logger=logger)
    return result


def s3_object_store(errors: list[str],
                    prefix: str | Path,
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
    :param prefix: the path specifying the location to store the object at
    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadatatagsdescribing the object
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the object was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # serialize the object
    data: bytes | None = None
    try:
        data = pickle.dumps(obj=obj)
    except Exception as e:
        _except_msg(errors=errors,
                    exception=e,
                    engine="aws",
                    logger=logger)

    # was the data obtained ?
    if data:
        # yes, store the serialized object
        result = s3_data_store(errors=errors,
                               prefix=prefix,
                               identifier=identifier,
                               data=data,
                               length=len(data),
                               mimetype=MIMETYPE_BINARY,
                               tags=tags,
                               bucket=bucket,
                               engine=engine,
                               client=client,
                               logger=logger)
    return result


def s3_item_exists(errors: list[str],
                   prefix: str | Path,
                   identifier: str = None,
                   bucket: str = None,
                   engine: str = None,
                   client: Any = None,
                   logger: Logger = None) -> bool:
    """
    Determine if a given item exists in the S3 store.

    The item might be interpreted as unspecified data, a file,
    an object, or, if *identifier* is not provided, a path-specified folder.
    Note that the S3 standard does not allow for empty folders (that is, prefixes not in use by objects).

    :param errors: incidental error messages
    :param prefix: the path specifying where to locate the item
    :param identifier: optional item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the item was found, 'False' otherwise, 'None' if error
    """
    # initialize the return variable
    result: bool | None = None

    # initialize the local errors list
    op_errors: list[str] = []

    # has 'identifier' been specified ?
    if identifier:
        # yes, get info about this object
        item_info: dict[str, Any] = s3_item_get_info(errors=op_errors,
                                                     bucket=bucket,
                                                     prefix=prefix,
                                                     identifier=identifier,
                                                     engine=engine,
                                                     client=client,
                                                     logger=logger)
        if op_errors:
            errors.extend(op_errors)
        else:
            result = isinstance(item_info, dict) and len(item_info) > 0
    else:
        # no, list at most one item in this folder
        items_data: list[dict[str, Any]] = s3_items_list(errors=op_errors,
                                                         prefix=prefix,
                                                         max_count=1,
                                                         bucket=bucket,
                                                         engine=engine,
                                                         client=client,
                                                         logger=logger)
        if op_errors:
            errors.extend(op_errors)
        else:
            result = isinstance(items_data, list) and len(items_data) > 0

    return result


def s3_item_get_info(errors: list[str],
                     prefix: str | Path,
                     identifier: str,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> Any:
    """
    Retrieve and return the information about an item in the S3 store.

    The item might be interpreted as unspecified data, a file, or an object.
    The information returned depends on the *engine* in question, and can be viewed
    at the native invocation's *docstring*.

    :param errors: incidental error messages
    :param prefix: the path specifying where to locate the item
    :param identifier: the item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information about the item, or 'None' if error or item not found
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
        result = aws_pomes.item_get_info(errors=op_errors,
                                         bucket=bucket,
                                         prefix=prefix,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.item_get_info(errors=op_errors,
                                           bucket=bucket,
                                           prefix=prefix,
                                           identifier=identifier,
                                           client=client,
                                           logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_item_get_tags(errors: list[str],
                     prefix: str | Path,
                     identifier: str,
                     bucket: str = None,
                     engine: str = None,
                     client: Any = None,
                     logger: Logger = None) -> dict:
    """
    Retrieve and return the existing metadata tags for an item in the S3 store.
    
    The item might be interpreted as unspecified data, a file, or an object.
    If item has no associated metadata tags, an empty *dict* is returned.
    The information returned depends on the *engine* in question, and can be viewed
    at the native invocation's *docstring*.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to retrieve the item from
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata tags associated with the item, or 'None' if error or item not found
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
        result = aws_pomes.item_get_tags(errors=op_errors,
                                         bucket=bucket,
                                         prefix=prefix,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.item_get_tags(errors=op_errors,
                                           bucket=bucket,
                                           prefix=prefix,
                                           identifier=identifier,
                                           client=client,
                                           logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_item_remove(errors: list[str],
                   prefix: str | Path,
                   identifier: str,
                   bucket: str = None,
                   engine: str = None,
                   client: Any = None,
                   logger: Logger = None) -> int:
    """
    Remove an item from the S3 store.

    The item might be interpreted as unspecified data, a file, or an object.
    To remove items in a given folder, use *s3_items_remove()*, instead.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to remove the item from
    :param identifier: the item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

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
                                       prefix=prefix,
                                       identifier=identifier,
                                       client=client,
                                       logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.item_remove(errors=op_errors,
                                         bucket=bucket,
                                         prefix=prefix,
                                         identifier=identifier,
                                         client=client,
                                         logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_items_list(errors: list[str],
                  prefix: str | Path,
                  max_count: int = None,
                  bucket: str = None,
                  engine: str = None,
                  client: Any = None,
                  logger: Logger = None) -> list[dict[str, Any]]:
    """
    Retrieve and return information on a list of items in *prefix*, in the S3 store.

    The information returned depends on the *engine* in question, and can be viewed
    at the native invocation's *docstring*. The first element in the list is the
    folder indicated in *prefix*.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to iterate from
    :param max_count: the maximum number of items to return (defaults to 1000)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information on a list of items, or 'None' if error or path not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

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
                                      prefix=prefix,
                                      max_count=max_count or 1000,
                                      client=client,
                                      logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.items_list(errors=op_errors,
                                        bucket=bucket,
                                        prefix=prefix,
                                        max_count=max_count or 1000,
                                        client=client,
                                        logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result


def s3_items_remove(errors: list[str],
                    prefix: str | Path,
                    max_count: int,
                    bucket: str = None,
                    engine: str = None,
                    client: Any = None,
                    logger: Logger = None) -> int:
    """
    Recursively remove up to *max_count* items in a folder, from the S3 store.

    The removal process is aborted if an error occurs.

    :param errors: incidental error messages
    :param prefix: the path specifying the location to remove the items from
    :param max_count: the maximum number of items to remove
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

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
        result = aws_pomes.items_remove(errors=op_errors,
                                        bucket=bucket,
                                        prefix=prefix,
                                        max_count=max_count,
                                        client=client,
                                        logger=logger)
    elif curr_engine == "minio":
        from . import minio_pomes
        result = minio_pomes.items_remove(errors=op_errors,
                                          bucket=bucket,
                                          prefix=prefix,
                                          max_count=max_count,
                                          client=client,
                                          logger=logger)
    # acknowledge local errors
    errors.extend(op_errors)

    return result
