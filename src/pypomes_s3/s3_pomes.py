import pickle
from logging import Logger
from pathlib import Path
from pypomes_core import Mimetype
from typing import Any, BinaryIO

from .s3_common import (
    _S3_ACCESS_DATA, _S3_LOGGERS, S3Engine, S3Param,
    _assert_engine, _get_param, _except_msg
)


def s3_setup(engine: S3Engine,
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

    :param engine: the S3 engine (one of [*aws*, *minio*])
    :param endpoint_url: the access URL for the service
    :param bucket_name: the name of the default bucket
    :param access_key: the access key for the service
    :param secret_key: the access secret code
    :param region_name: the name of the region where the engine is located
    :param secure_access: whether to use Transport Security Layer
    :return: *True* if the data were accepted, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # process te parameters
    if engine in S3Engine and \
       endpoint_url and bucket_name and \
       access_key and secret_key:
        _S3_ACCESS_DATA[engine] = {
            S3Param.ENGINE: engine.value,
            S3Param.ENDPOINT_URL: endpoint_url,
            S3Param.BUCKET_NAME: bucket_name,
            S3Param.ACCESS_KEY: access_key,
            S3Param.SECRET_KEY: secret_key,
            S3Param.SECURE_ACCESS: secure_access,
            S3Param.REGION_NAME: region_name,
            S3Param.VERSION: ""
        }
        result = True

    return result


def s3_set_logger(engine: S3Engine = None,
                  logger: Logger = None) -> bool:
    """
    Establish the logger for logging operations involving *engine*.

    This operation must be invoked after *engine* has been configured. If specified,
    *engine* must be one of [*aws*, *minio*].

    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param logger: the logger for the S3 engine
    :return: *True* if the logger was estabished, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # assert the database engine
    engine = _assert_engine(engine=engine)
    if engine:
        _S3_LOGGERS[engine] = logger
        result = True

    return result


def s3_get_engines() -> list[S3Engine]:
    """
    Retrieve the *list* of configured engines.

    This *list* may include any of the supported engines: *aws*, *minio*.
    Note that the values in the returned *list* are instances of *S3Engine*, not strings.

    :return: the *list* of configured engines
    """
    # SANITY-CHECK: return a cloned 'list'
    return list(_S3_ACCESS_DATA)


def s3_get_param(key: S3Param,
                 engine: S3Engine = None) -> str | None:
    """
    Return the connection parameter value for *key*.

    The *key* should be one of *endpoint-url*, *bucket-name*, *access-key*, *secret-key*,
    and *secure-access*. For *aws*, the extra key *region-name* may be used.

    :param key: the connection parameter
    :param engine: the reference S3 engine (the default engine, if not provided)
    :return: the current value of the connection parameter, or *None* if not found
    """
    # assert the S3 engine
    engine = next(iter(_S3_ACCESS_DATA)) if not engine and _S3_ACCESS_DATA else engine

    # retrieve the connection parameter
    return _get_param(engine=engine,
                      param=key)


def s3_get_params(engine: S3Engine = None) -> dict[S3Param, Any] | None:
    """
    Return the current access parameters as a *dict*.

    The returned *dict* contains the keys *endpoint-url*, *bucket-name*,
    *access-key*, *secret-key*, *region-name*, and *secure-access*.
    The meaning of these parameters may vary between different S3 engines.
    Note that the keys in the returned *dict* are strings, not *S3Param* instances.

    :param engine: the database engine
    :return: the current connection parameters for the engine, or *None* if not found
    """
    # assert the S3 engine
    engine = next(iter(_S3_ACCESS_DATA)) if not engine and _S3_ACCESS_DATA else engine

    # return the connection parameters
    return _S3_ACCESS_DATA[engine].copy() if engine in _S3_ACCESS_DATA else None


def s3_startup(engine: S3Engine = None,
               bucket: str = None,
               errors: list[str] = None) -> bool:
    """
    Prepare the S3 client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the S3 service is fully functional.

    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if service is fully functional, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have an errors list
    if not isinstance(errors, list):
        errors = []

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if not errors:
        # determine if 'curr_engine' has been prepared for operations
        version: str = _S3_ACCESS_DATA[curr_engine].get(S3Param.VERSION)
        if version:
            result = True
        else:
            # make sure to have a bucket
            bucket = bucket or _get_param(engine=curr_engine,
                                          param=S3Param.BUCKET_NAME)
            if curr_engine == S3Engine.AWS:
                from . import aws_pomes
                result = aws_pomes.startup(bucket=bucket,
                                           errors=errors)
            elif curr_engine == S3Engine.MINIO:
                from . import minio_pomes
                result = minio_pomes.startup(bucket=bucket,
                                             errors=errors)
            if not errors:
                _S3_ACCESS_DATA[curr_engine][S3Param.VERSION] = __get_version(engine=curr_engine)

    return result


def s3_get_client(engine: S3Engine = None,
                  errors: list[str] = None) -> Any:
    """
    Obtain and return a client to *engine*, or *None* if the client cannot be obtained.

    The target S3 engine, default or specified, must have been previously configured.

    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the client to the S3 engine, or *None* if the client cannot be obtained
    """
    # initialize the return variable
    result: Any = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.get_client(errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.get_client(errors=errors)
    return result


def s3_data_retrieve(identifier: str,
                     prefix: str | Path = None,
                     data_range: tuple[int, int] = None,
                     bucket: str = None,
                     engine: S3Engine = None,
                     client: Any = None,
                     errors: list[str] = None) -> bytes | None:
    """
    Retrieve data from the *S3* store.

    :param identifier: the data identifier
    :param prefix: optional path prefixing the item to be retrieved
    :param data_range: the begin-end positions within the data (in bytes, defaults to *None* - all bytes)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the bytes retrieved, or *None* if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.data_retrieve(identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         data_range=data_range,
                                         client=client,
                                         errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.data_retrieve(identifier=identifier,
                                           prefix=prefix,
                                           bucket=bucket,
                                           data_range=data_range,
                                           client=client,
                                           errors=errors)
    return result


def s3_data_store(identifier: str,
                  data: bytes | str | BinaryIO,
                  length: int,
                  prefix: str | Path = None,
                  mimetype: Mimetype | str = Mimetype.BINARY,
                  tags: dict = None,
                  bucket: str = None,
                  engine: S3Engine = None,
                  client: Any = None,
                  errors: list[str] = None) -> dict[str, str] | None:
    """
    Store data at the *S3* store.

    In case *length* cannot be determined, it should be set to *-1* (*MinIO*), or to *None* (*AWS*).

    On success, this operation returns a *dict* with information related to the stored item.
    Unfortunately, it is not possible to detail the information returned, as there is no consistency
    in the responses. In fact, the responses vary wildly with the different *S3* implementations.
    It should also be noted that those responses are not guaranteed to be serializable.

    :param identifier: the data identifier
    :param data: the data to store
    :param length: the length of the data
    :param prefix: optional path prefixing the item holding the data
    :param mimetype: the data mimetype, defaults to *BINARY*
    :param tags: optional metadata tags describing the data
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: stored item's properties, or *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.data_store(identifier=identifier,
                                      data=data,
                                      bucket=bucket,
                                      prefix=prefix,
                                      length=length,
                                      mimetype=mimetype,
                                      tags=tags,
                                      client=client,
                                      errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.data_store(identifier=identifier,
                                        data=data,
                                        bucket=bucket,
                                        prefix=prefix,
                                        length=length,
                                        mimetype=mimetype,
                                        tags=tags,
                                        client=client,
                                        errors=errors)
    return result


def s3_file_retrieve(identifier: str,
                     filepath: Path | str,
                     bucket: str = None,
                     prefix: str | Path = None,
                     engine: S3Engine = None,
                     client: Any = None,
                     errors: list[str] = None) -> bool | None:
    """
    Retrieve a file from the *S3* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to retrieve as a file
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the file was retrieved, *False* otherwise, or *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.file_retrieve(identifier=identifier,
                                         filepath=filepath,
                                         bucket=bucket,
                                         prefix=prefix,
                                         client=client,
                                         errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.file_retrieve(identifier=identifier,
                                           filepath=filepath,
                                           bucket=bucket,
                                           prefix=prefix,
                                           client=client,
                                           errors=errors)
    return result


def s3_file_store(identifier: str,
                  filepath: Path | str,
                  mimetype: Mimetype | str,
                  tags: dict = None,
                  bucket: str = None,
                  prefix: str | Path = None,
                  engine: S3Engine = None,
                  client: Any = None,
                  errors: list[str] = None) -> bool:
    """
    Store a file at the *S3* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: optional path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata tags describing the file
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item holding the file data
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the file was successfully stored, *False* if error
    """
    # initialize the return variable
    result: bool = False

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.file_store(identifier=identifier,
                                      filepath=filepath,
                                      mimetype=mimetype,
                                      bucket=bucket,
                                      prefix=prefix,
                                      tags=tags,
                                      client=client,
                                      errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.file_store(identifier=identifier,
                                        filepath=filepath,
                                        mimetype=mimetype,
                                        bucket=bucket,
                                        prefix=prefix,
                                        tags=tags,
                                        client=client,
                                        errors=errors)
    return result


def s3_object_retrieve(identifier: str,
                       bucket: str = None,
                       prefix: str | Path = None,
                       engine: S3Engine = None,
                       client: Any = None,
                       errors: list[str] = None) -> Any:
    """
    Retrieve an object from the *S3* store.

    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to retrieve as object
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the object retrieved, or *None* if error or object not found
    """
    # initialize the return variable
    result: Any = None

    # retrieve the data
    data: bytes = s3_data_retrieve(identifier=identifier,
                                   bucket=bucket,
                                   prefix=prefix,
                                   engine=engine,
                                   client=client,
                                   errors=errors)
    # was the data obtained ?
    if data:
        # yes, umarshall the corresponding object
        try:
            result = pickle.loads(data)
        except Exception as e:
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e,
                                          engine=engine))
    return result


def s3_object_store(identifier: str,
                    obj: Any,
                    tags: dict = None,
                    bucket: str = None,
                    prefix: str | Path = None,
                    engine: S3Engine = None,
                    client: Any = None,
                    errors: list[str] = None) -> dict[str, str] | None:
    """
    Store an object at the *S3* store.

    On success, this operation returns a *dict* with the following properties related to the stored item:
      - *object_name*: The name of the object that was uploaded
      - *version_id*: The version ID of the object, if versioning is enabled on the bucket
      - *etag*: The entity tag (ETag) of the object, which is a unique identifier for the object's content

    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadatatagsdescribing the object
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item holding the the object
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the stored item's properties listed above, or *None* if error
    """
    # initialize the return variable
    result: dict[str, str] | None = None

    # serialize the object
    data: bytes | None = None
    try:
        data = pickle.dumps(obj=obj)
    except Exception as e:
        if isinstance(errors, list):
            errors.append(_except_msg(exception=e,
                                      engine=engine))
    # was the data obtained ?
    if data:
        # yes, store the serialized object
        result = s3_data_store(identifier=identifier,
                               data=data,
                               length=len(data),
                               mimetype=Mimetype.BINARY,
                               tags=tags,
                               bucket=bucket,
                               prefix=prefix,
                               engine=engine,
                               client=client,
                               errors=errors)
    return result


def s3_item_exists(identifier: str,
                   prefix: str | Path = None,
                   bucket: str = None,
                   engine: S3Engine = None,
                   client: Any = None,
                   errors: list[str] = None) -> bool | None:
    """
    Determine if a given item exists in the *S3* store.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item to be located
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the item was found, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # get info about this object
    item_info: dict[str, Any] = s3_item_get_info(identifier=identifier,
                                                 prefix=prefix,
                                                 bucket=bucket,
                                                 engine=engine,
                                                 client=client,
                                                 errors=errors)
    if item_info:
        result = isinstance(item_info, dict) and len(item_info) > 0

    return result


def s3_item_get_info(identifier: str,
                     prefix: str | Path = None,
                     bucket: str = None,
                     engine: S3Engine = None,
                     client: Any = None,
                     errors: list[str] = None) -> Any:
    """
    Retrieve the information about an item in the *S3* store.

    The information returned depends on the *engine* in question, and can be viewed at the
    native invocation's *docstring*.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: information about the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: Any | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.item_get_info(identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.item_get_info(identifier=identifier,
                                           prefix=prefix,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    return result


def s3_item_get_tags(identifier: str,
                     prefix: str | Path = None,
                     bucket: str = None,
                     engine: S3Engine = None,
                     client: Any = None,
                     errors: list[str] = None) -> dict[str, Any] | None:
    """
    Retrieve the existing metadata tags for an item in the *S3* store.

    If item has no associated metadata tags, an empty *dict* is returned. The information returned depends
    on the *engine* in question, and can be viewed at the native invocation's *docstring*.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the metadata tags associated with the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.item_get_tags(identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.item_get_tags(identifier=identifier,
                                           prefix=prefix,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    return result


def s3_item_remove(identifier: str,
                   prefix: str | Path = None,
                   version: str = None,
                   bucket: str = None,
                   engine: S3Engine = None,
                   client: Any = None,
                   errors: list[str] = None) -> int | None:
    """
    Remove an item from the *S3* store.

    If *version* is not specified, then only the item's current (latest) version is removed.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the items to be removed
    :param version: optional version of the item to be removed (defaults to the its current version)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the item was successfully removed, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.item_remove(identifier=identifier,
                                       prefix=prefix,
                                       version=version,
                                       bucket=bucket,
                                       client=client,
                                       errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.item_remove(identifier=identifier,
                                         prefix=prefix,
                                         version=version,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    return result


def s3_items_remove(identifiers: list[str | tuple[str, str]],
                    prefix: str | Path = None,
                    bucket: str = None,
                    engine: S3Engine = None,
                    client: Any = None,
                    errors: list[str] = None) -> int:
    """
    Remove the items listed in *identifiers* from the *S3* store.

    The items to be removed are listed in *identifiers*, either with a simple *name*, or with
    a *name,version* pair. If the version is not provided for a given item, then only its
    current (latest) version is removed. Items in *identifiers* are ignored, if not found.

    The removal operation will attempt to continue if errors occur. Thus, make sure to check *errors*,
    besides inspecting the returned value.

    :param identifiers: identifiers for the items to be removed (defaults to all items in *prefix*)
    :param prefix: optional path prefixing the items to be removed
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.items_remove(identifiers=identifiers,
                                        bucket=bucket,
                                        prefix=prefix,
                                        client=client,
                                        errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.items_remove(identifiers=identifiers,
                                          bucket=bucket,
                                          prefix=prefix,
                                          client=client,
                                          errors=errors)
    return result


def s3_prefix_count(prefix: str | Path | None,
                    bucket: str = None,
                    engine: S3Engine = None,
                    client: Any = None,
                    errors: list[str] = None) -> int | None:
    """
    Retrieve the number of items prefixed with *prefix*, in the *S3* store.

    If *prefix* is not specified, then the bucket's root is used. A count operation on the contents
    of a *prefix* may be time-consuming, in *AWS* storages, and extremely so, in *MinIO* storages.

    :param prefix: path prefixing the items to be counted
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the number of items in *prefix*, 0 if *prefix* not found, or *None* if error
    """
    # initialize the return variable
    result: int | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.prefix_count(bucket=bucket,
                                        prefix=prefix,
                                        client=client,
                                        errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.prefix_count(bucket=bucket,
                                          prefix=prefix,
                                          client=client,
                                          errors=errors)
    return result


def s3_prefix_list(prefix: str | Path,
                   max_count: int = None,
                   start_after: str = None,
                   bucket: str = None,
                   engine: S3Engine = None,
                   client: Any = None,
                   errors: list[str] = None) -> list[dict[str, Any]] | None:
    """
    Recursively retrieve and return information on a list of items prefixed with *prefix*, in the *S3* store.

    If *prefix* is not specified, then the bucket's root is used. If *max_count* is a positive integer,
    the number of items returned may be less, but not more, than its value, otherwise it is ignored, and
    all existing items in *prefix* are returned. Optionally, *start_after* identifies the item after which
    the listing must start, thus allowing for paginating the items retrieval operation.

    The information returned depends on the *engine* in question, and can be viewed at the native
    invocation's *docstring*.

    :param prefix: path prefixing the items to be listed
    :param max_count: the maximum number of items to return (defaults to all items)
    :param start_after: optionally identifies the item after which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: information on a list of items in *prefix*, or *None* if error or *prefix* not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.prefix_list(prefix=prefix,
                                       max_count=max_count,
                                       start_after=start_after,
                                       bucket=bucket,
                                       client=client,
                                       errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.prefix_list(prefix=prefix,
                                         max_count=max_count,
                                         start_after=start_after,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    return result


def s3_prefix_remove(prefix: str | Path | None,
                     bucket: str = None,
                     engine: S3Engine = None,
                     client: Any = None,
                     errors: list[str] = None) -> int:
    """
    Remove the items prefixed with *prefix* from the *S3* store.

    If *prefix* is not specified, then the bucket's root is used. Note that, at S3 storages,
    prefixes are visual representations, and as such disappear when not in use. The removal operation
    will attempt to continue if errors occur. Thus, make sure to check *errors*, besides inspecting
    the returned value.

    :param prefix: path prefixing the items to be removed
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the S3 engine to use (uses the default engine, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    # determine the S3 engine
    curr_engine: S3Engine = _assert_engine(engine=engine,
                                           errors=errors)
    if curr_engine == S3Engine.AWS:
        from . import aws_pomes
        result = aws_pomes.prefix_remove(prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    elif curr_engine == S3Engine.MINIO:
        from . import minio_pomes
        result = minio_pomes.prefix_remove(prefix=prefix,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    return result


def __get_version(engine: S3Engine = None) -> str | None:
    """
    Obtain and return the current version of *engine*.

    :param engine: the reference S3 engine (the default engine, if not provided)
    :return: the engine's current version, or *None* if not found
    """
    # initialize the return variable
    result: str | None = None

    # assert the S3 engine
    engine = next(iter(_S3_ACCESS_DATA)) if not engine and _S3_ACCESS_DATA else engine

    match engine:
        case S3Engine.MINIO:
            import minio
            result = minio.__version__
        case S3Engine.AWS:
            import boto3
            result = boto3.__version__

    return result
