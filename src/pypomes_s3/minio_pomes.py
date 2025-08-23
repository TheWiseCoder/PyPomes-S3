from collections.abc import Iterator
from io import BytesIO
from logging import Logger
from minio import Minio
from minio.commonconfig import Tags
from minio.datatypes import Object as MinioObject
from minio.deleteobjects import DeleteObject, DeleteError
from minio.helpers import ObjectWriteResult
from pathlib import Path
from pypomes_core import Mimetype, obj_to_dict
from typing import Any, BinaryIO
from urllib3.response import HTTPResponse

from .s3_common import (
    S3Engine, S3Param,
    _get_param, _get_params, _normalize_tags, _except_msg
)


def startup(bucket: str,
            errors: list[str] | None,
            logger: Logger = None) -> bool:
    """
    Prepare the *MinIO* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the MinIo service is fully functional.

    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: *True* if service is fully functional, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # obtain a client
    client: Minio = get_client(errors=errors,
                               logger=logger)
    # was the client obtained ?
    if client:
        # yes, proceed
        try:
            if client.bucket_exists(bucket_name=bucket):
                action: str = "asserted"
            else:
                client.make_bucket(bucket_name=bucket)
                action: str = "created"
            result = True
            if logger:
                logger.debug(msg=f"Started MinIO, {action} bucket '{bucket}'")
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.MINIO)
            if logger:
                logger.error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)
    return result


def get_client(errors: list[str] | None,
               logger: Logger = None) -> Minio | None:
    """
    Obtain and return a *MinIO* client object.

    :param errors: incidental error messages
    :param logger: optional logger
    :return: the MinIO client object, or *None* if error
    """
    # initialize the return variable
    result: Minio | None = None

    # retrieve the access parameters
    minio_params: dict[S3Param, Any] = _get_params(engine=S3Engine.MINIO)

    # obtain the MinIO client
    try:
        result = Minio(access_key=minio_params.get(S3Param.ACCESS_KEY),
                       secret_key=minio_params.get(S3Param.SECRET_KEY),
                       endpoint=minio_params.get(S3Param.ENDPOINT_URL),
                       secure=minio_params.get(S3Param.SECURE_ACCESS),
                       region=minio_params.get(S3Param.REGION_NAME))
        if logger:
            logger.debug(msg="Minio client created")

    except Exception as e:
        msg: str = _except_msg(exception=e,
                               engine=S3Engine.MINIO)
        if logger:
            logger.error(msg=msg)
        if isinstance(errors, list):
            errors.append(msg)
    return result


def data_retrieve(identifier: str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  data_range: tuple[int, int] = None,
                  client: Minio = None,
                  errors: list[str] = None,
                  logger: Logger = None) -> bytes | None:
    """
    Retrieve data from the *MinIO* store.

    :param identifier: the data identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to be retrieved
    :param data_range: the begin-end positions within the data (in bytes, defaults to *None* - all bytes)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: the bytes retrieved, or *None* if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        offset: int = data_range[0] if data_range else 0
        length: int = data_range[1] - data_range[0] + 1 if data_range else 0

        # retrieve the data
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_name: str = obj_path.as_posix()
            else:
                obj_name: str = identifier
            response: HTTPResponse = client.get_object(bucket_name=bucket,
                                                       object_name=obj_name,
                                                       offset=offset,
                                                       length=length)
            result = response.data
            if logger:
                logger.debug(msg=f"Retrieved '{obj_name}', bucket '{bucket}'")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if not (hasattr(e, "code") and e.code == "NoSuchKey"):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.MINIO)
                if logger:
                    logger.error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def data_store(identifier: str,
               data: bytes | str | BinaryIO,
               length: int,
               prefix: str | Path = None,
               mimetype: Mimetype | str = Mimetype.BINARY,
               tags: dict[str, str] = None,
               bucket: str = None,
               client: Minio = None,
               errors: list[str] = None,
               logger: Logger = None) -> dict[str, str] | None:
    """
    Store *data* at the *MinIO* store.

    In case *length* cannot be determined, it should be set to *-1*.

    On success, this operation returns a *dict* obtained from converting the
    *ObjectWriteResult* object returned from the native invocation.

    :param identifier: the data identifier
    :param data: the data to store
    :param length: the length of the data
    :param prefix: optional path prefixing the item holding the data
    :param mimetype: the data mimetype, defaults to *BINARY*
    :param tags: optional metadata tags describing the file
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: the stored item's properties listed above, or *None* if error
    """
    # initialize the return variable
    result: dict[str, str] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        bin_data: BinaryIO
        if isinstance(data, BinaryIO):
            bin_data = data
        else:
            bin_data = BytesIO(data) if isinstance(data, bytes) else \
                       BytesIO(bytes(data, "utf-8"))
            bin_data.seek(0)
        tags = _minio_tags(tags)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_name: str = obj_path.as_posix()
            else:
                obj_name: str = identifier
            if isinstance(mimetype, Mimetype):
                mimetype = mimetype.value
            reply: ObjectWriteResult = client.put_object(bucket_name=bucket,
                                                         object_name=obj_name,
                                                         data=bin_data,
                                                         length=length,
                                                         content_type=mimetype,
                                                         tags=tags)
            if reply:
                # convert 'reply' to a 'dict'
                result = obj_to_dict(obj=reply)
                if logger:
                    logger.debug(msg=(f"Stored '{obj_name}', bucket '{bucket}', "
                                      f"content type '{mimetype}', tags '{tags}'"))
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.MINIO)
            if logger:
                logger.error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)

    return result


def file_retrieve(identifier: str,
                  filepath: Path | str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  client: Minio = None,
                  errors: list[str] = None,
                  logger: Logger = None) -> bool | None:
    """
    Retrieve a file from the *MinIO* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to retrieve as a file
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: *True* if the file was retrieved, *False* otherwise, or *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_name: str = obj_path.as_posix()
            else:
                obj_name: str = identifier
            file_path: str = Path(filepath).as_posix()
            client.fget_object(bucket_name=bucket,
                               object_name=obj_name,
                               file_path=file_path)
            result = Path(filepath).exists()
            if logger:
                logger.debug(msg=f"{obj_name}', bucket '{bucket}', "
                                 f"{'retrieved' if result else 'not retrieved'}")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if not (hasattr(e, "code") and e.code == "NoSuchKey"):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.MINIO)
                if logger:
                    logger.error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def file_store(identifier: str,
               filepath: Path | str,
               mimetype: Mimetype | str,
               bucket: str = None,
               prefix: str | Path = None,
               tags: dict[str, str] = None,
               client: Minio = None,
               errors: list[str] = None,
               logger: Logger = None) -> bool:
    """
    Store a file at the *MinIO* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: optional path specifying where the file is
    :param mimetype: the file mimetype
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item holding the file data
    :param tags: optional metadata tags describing the file
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: *True* if the file was successfully stored, *False* if error
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        tags = _minio_tags(tags)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_name: str = obj_path.as_posix()
            else:
                obj_name: str = identifier
            file_path: str = Path(filepath).as_posix()
            if isinstance(mimetype, Mimetype):
                mimetype = mimetype.value
            _reply: ObjectWriteResult = client.fput_object(bucket_name=bucket,
                                                           object_name=obj_name,
                                                           file_path=file_path,
                                                           content_type=mimetype,
                                                           tags=tags)
            if logger:
                logger.debug(msg=(f"Stored '{obj_name}', bucket '{bucket}', "
                                  f"from '{file_path}', content type '{mimetype}', tags '{tags}'"))
            result = True
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.MINIO)
            if logger:
                logger.error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)

    return result


def item_get_info(identifier: str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  client: Minio = None,
                  errors: list[str] = None,
                  logger: Logger = None) -> dict[str, Any] | None:
    """
    Retrieve information about an item in the *MinIO* store.

    The item might be interpreted as unspecified data, a file, or an object.
    The information about the item might include:
        - *last_modified*: the date and time the item was last modified
        - *size*: the size of the item in bytes
        - *etag*: a hash of the item
        - *is_dir*: a *bool* indicating if the item is a directory
        - *version_id*: the version of the item, if bucket versioning is enabled

    :param identifier: the item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying where to locate the item
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: information about the item, an empty 'dict' if item not found, or *None* if error
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_name: str = obj_path.as_posix()
            else:
                obj_name: str = identifier
            stats: MinioObject = client.stat_object(bucket_name=bucket,
                                                    object_name=obj_name)
            result = vars(stats)
            if logger:
                logger.debug(msg=f"Got info for '{obj_name}', bucket '{bucket}'")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if not (hasattr(e, "code") and e.code == "NoSuchKey"):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.MINIO)
                if logger:
                    logger.error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def item_get_tags(identifier: str,
                  prefix: str | Path = None,
                  bucket: str = None,
                  client: Minio = None,
                  errors: list[str] = None,
                  logger: Logger = None) -> dict[str, str] | None:
    """
    Retrieve the existing metadata tags for an item in the *MinIO* store.

    If item was not found, or has no associated metadata tags, an empty *dict* is returned.

    :param identifier: the object identifier
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: the metadata tags, an empty 'dict' if item not found os has no tags, or *None* if error
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_name: str = obj_path.as_posix()
            else:
                obj_name: str = identifier
            tags: Tags = client.get_object_tags(bucket_name=bucket,
                                                object_name=obj_name)
            if tags:
                result = dict(tags.items())
            else:
                result = {}
            if logger:
                logger.debug(msg=f"Retrieved '{obj_name}', bucket '{bucket}', tags '{result}'")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if not (hasattr(e, "code") and e.code == "NoSuchKey"):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.MINIO)
                if logger:
                    logger.error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def item_remove(identifier: str,
                prefix: str | Path = None,
                version: str = None,
                bucket: str = None,
                client: Minio = None,
                errors: list[str] = None,
                logger: Logger = None) -> bool | None:
    """
    Remove an item from the *MinIO* store.

    If *version* is not specified, then only the item's current (latest) version is removed.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item to be removed
    :param version: optional version of the item to be removed (defaults to the its current version)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: *True* if the item was successfully removed, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = False

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)

        path: Path = Path(prefix) / identifier
        name: str = path.as_posix()
        # remove the item
        try:
            client.remove_object(bucket_name=bucket,
                                 object_name=name,
                                 version_id=version)
            if logger:
                logger.debug(msg=f"Removed item '{name}', bucket '{bucket}'")
            result = True
        except Exception as e:
            result = None
            # noinspection PyUnresolvedReferences
            if not (hasattr(e, "code") and e.code == "NoSuchKey"):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.MINIO)
                if logger:
                    logger.error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def items_remove(identifiers: list[str | tuple[str, str]],
                 prefix: str | Path = None,
                 bucket: str = None,
                 client: Minio = None,
                 errors: list[str] = None,
                 logger: Logger = None) -> int:
    """
    Remove the items listed in *identifiers* from the *MinIO* store.

    The items to be removed are listed in *identifiers*, either with a simple *name*, or with
    a *name,version* pair. If the version is not provided for a given item, then only its
    current (latest) version is removed. Items in *identifiers* are ignored, if not found.

    The removal operation will attempt to continue if errors occur. Thus, make sure to check *errors*,
    besides inspecting the returned value.

    :param identifiers: identifiers for the items to be removed (defaults to all items in *prefix*)
    :param prefix: optional path prefixing the items to be removed
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        # establish a path prefix
        path: Path = Path(prefix) if isinstance(prefix, str) else prefix

        # a maximum of 1000 items is used for convenience
        pos: int = 0
        size: int = min(1000, len(identifiers))
        while size > 0:
            deletes: list[DeleteObject] = []
            for identifier in identifiers[pos:pos+size]:
                if isinstance(identifier, tuple):
                    deletes.append(DeleteObject(name=(path / identifier[0]).as_posix() if path else identifier[0],
                                                version_id=identifier[1]))
                else:
                    # noinspection PyTypeChecker
                    deletes.append(DeleteObject(name=(path / identifier).as_posix() if path else identifier))
            try:
                reply: Iterator[DeleteError] = client.remove_objects(bucket_name=bucket,
                                                                     delete_object_list=deletes)
                # acknowledge errors eventually reported
                if isinstance(errors, list):
                    errors.extend([f"Error {e.code} ({e.message}) "
                                   f"removing document ({e.name}, v. {e.version_id}"
                                   for e in (reply or [])])
            except Exception as e:
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.MINIO)
                if logger:
                    logger.error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
            pos += size
            size = min(1000, len(identifiers) - pos)

    return result


def prefix_count(prefix: str | Path | None,
                 bucket: str = None,
                 client: Minio = None,
                 errors: list[str] = None,
                 logger: Logger = None) -> int | None:
    """
    Retrieve the number of items prefixed with *prefix*, in the *MinIO* store.

    If *prefix* is not specified, then the bucket's root is used. A count operation on the contents
    of a *prefix* may be extremely time-consuming, as the only way to obtain such information with
    the *minio* package is by retrieving and counting the elements from the appropriate iterators.

    :param prefix: path prefixing the items to be counted
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional AWS client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: the number of items in *prefix*, 0 if *prefix* not found, or *None* if error
    """
    # initialize the return variable
    result: int | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        obj_path: str = Path(prefix).as_posix()
        try:
            count: int = 0
            proceed: bool = True
            continuation: str | None = None
            while proceed:
                # obtain an iterator on the items in the folder
                iterator: Iterator = client.list_objects(bucket_name=bucket,
                                                         prefix=obj_path,
                                                         include_user_meta=True,
                                                         recursive=True,
                                                         start_after=continuation)
                # traverse the iterator (it might be empty)
                proceed = False
                for obj in iterator:
                    count += 1
                    continuation = obj.object_name
                    proceed = True

            # save the count and log the results
            result = count
            if logger:
                logger.debug(msg=f"Counted {result} items in '{prefix}', bucket '{bucket}'")
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.MINIO)
            if logger:
                logger.error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)

    return result


def prefix_list(prefix: str | Path,
                max_count: int = None,
                start_after: str = None,
                bucket: str = None,
                client: Minio = None,
                errors: list[str] = None,
                logger: Logger = None) -> list[dict[str, Any]] | None:
    """
    Recursively retrieve and return information on a list of items prefixed with *prefix*, in the *MinIO* store.

    If *prefix* is not specified, then the bucket's root is used. If *max_count* is a positive integer,
    the number of items returned may be less, but not more, than its value, otherwise it is ignored, and
    all existing items in *prefix* are returned. Optionally, *start_after* identifies the item after which
    the listing must start, thus allowing for paginating the items retrieval operation.

    The information returned by the native invocation is shown below, lexicographically sorted by *object_name*.
        - *object_name*: the name of the item
        - *last_modified*: the date and time the item was last modified
        - *size*: the size of the item in bytes
        - *etag*: a hash of the item
        - *is_dir*: a *bool* indicating if the item is a directory
        - *version_id*: the version of the item, if bucket versioning is enabled

    :param prefix: path prefixing the items to be listed
    :param max_count: the maximum number of items to return
    :param start_after: optionally identifies the item after which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: the iterator into the list of items, or *None* if path not found or error
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.MINIO,
                                      param=S3Param.BUCKET_NAME)
        # must terminate with '/', otherwise only the folder is considered
        path: str = Path(prefix).as_posix() + "/" if prefix else None
        try:
            items: list[dict[str, Any]] = []
            proceed: bool = True
            while proceed:
                # obtain an iterator on the items in the folder
                iterator: Iterator[MinioObject] = client.list_objects(bucket_name=bucket,
                                                                      prefix=path,
                                                                      include_user_meta=True,
                                                                      recursive=True,
                                                                      start_after=start_after)
                # traverse the iterator (it might be empty)
                proceed = False
                for obj in iterator:
                    items.append(vars(obj))
                    if max_count and len(items) == max_count:
                        break
                    start_after = obj.object_name
                    proceed = True

            # save the items and log the results
            result = items
            if logger:
                logger.debug(msg=f"Listed {len(result)} items in '{prefix}', bucket '{bucket}'")
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.MINIO)
            if logger:
                logger.error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)

    return result


def prefix_remove(prefix: str | Path | None,
                  bucket: str = None,
                  client: Minio = None,
                  errors: list[str] = None,
                  logger: Logger = None) -> int:
    """
    Remove the items prefixed with *prefix* from the *MinIO* store.

    If *prefix* is not specified, then the bucket's root is used. Note that, at S3 storages,
    prefixes are visual representations, and as such disappear when not in use. The removal operation
    will attempt to continue if errors occur. Thus, make sure to check *errors*, besides inspecting
    the returned value.

    :param prefix: path prefixing the items to be removed
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param errors: incidental error messages
    :param logger: optional logger
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        if not isinstance(errors, list):
            errors = []
        items: list[dict[str, Any]] = prefix_list(bucket=bucket,
                                                  prefix=prefix,
                                                  client=client,
                                                  errors=errors,
                                                  logger=logger)
        if not errors:
            # a maximum of 1000 items is used for convenience
            identifiers = [i.get("Key") for i in (items or [])]
            pos: int = 0
            size: int = min(1000, len(identifiers))
            while size > 0:
                deletes: list[DeleteObject] = []
                for identifier in identifiers[pos:pos+size]:
                    if isinstance(identifier, tuple):
                        deletes.append(DeleteObject(name=identifier[0],
                                                    version_id=identifier[1]))
                    else:
                        # noinspection PyTypeChecker
                        deletes.append(DeleteObject(name=identifier))
                try:
                    reply: Iterator[DeleteError] = client.remove_objects(bucket_name=bucket,
                                                                         delete_object_list=deletes)
                    # acknowledge errors eventually reported
                    if isinstance(errors, list):
                        errors.extend([f"Error {e.code} ({e.message}) "
                                       f"removing document ({e.name}, v. {e.version_id}"
                                       for e in (reply or [])])
                except Exception as e:
                    msg: str = _except_msg(exception=e,
                                           engine=S3Engine.MINIO)
                    if logger:
                        logger.error(msg=msg)
                    if isinstance(errors, list):
                        errors.append(msg)
                pos += size
                size = min(1000, len(identifiers) - pos)

    return result


def _minio_tags(tags: dict[str, str]) -> Tags:

    # initialize the return variable
    result: Tags | None = None

    # have tags been defined ?
    if tags:
        # yes, process them
        result = Tags(for_object=True)
        for key, value in _normalize_tags(tags=tags).items():
            result[key] = value

    return result
