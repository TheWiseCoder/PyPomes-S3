import pickle
import uuid
from collections.abc import Iterator
from io import BytesIO
from logging import Logger
from minio import Minio
from minio.datatypes import Object as MinioObject
from minio.commonconfig import Tags
from pathlib import Path
from pypomes_core import str_to_hex, str_from_hex
from pypomes_http import MIMETYPE_BINARY
from typing import Any, BinaryIO
from unidecode import unidecode
from urllib3.response import HTTPResponse

from .s3_common import (
    _get_param, _get_params, _except_msg, _log
)


def get_client(errors: list[str],
               logger: Logger = None) -> Minio:
    """
    Obtain and return a *MinIO* client object.

    :param errors: incidental error messages
    :param logger: optional logger
    :return: the MinIO client object
    """
    # initialize the return variable
    result: Minio | None = None

    # retrieve the access parameters
    (endpoint_url, bucket_name, temp_folder,
     access_key, secret_key, secure_access) = _get_params("minio")

    # obtain the MinIO client
    try:
        result = Minio(access_key=access_key,
                       secret_key=secret_key,
                       endpoint=endpoint_url,
                       secure=secure_access)
        _log(logger=logger,
             stmt="Minio client created")

    except Exception as e:
        _except_msg(errors=errors,
                    exception=e,
                    engine="minio",
                    logger=logger)
    return result


def startup(errors: list[str],
            bucket: str,
            logger: Logger = None) -> bool:
    """
    Prepare the *MinIO* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the MinIo service is fully functional.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param logger: optional logger
    :return: 'True' if service is fully functional, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # obtain a MinIO client
    client: Minio = get_client(errors=errors,
                               logger=logger)
    # was it obtained ?
    if client:
        # yes, proceed
        try:
            if not client.bucket_exists(bucket_name=bucket):
                client.make_bucket(bucket_name=bucket)
            result = True
            _log(logger=logger,
                 stmt=f"Started MinIO, bucket={bucket}")
        except Exception as e:
            _except_msg(errors=errors,
                        exception=e,
                        engine="minio",
                        logger=logger)
    return result


def data_store(errors: list[str],
               bucket: str,
               basepath: str | Path,
               identifier: str,
               data: bytes | str | BinaryIO,
               length: int = -1,
               mimetype: str = MIMETYPE_BINARY,
               tags: dict[str, str] = None,
               client: Minio = None,
               logger: Logger = None) -> bool:
    """
    Store *data* at the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to store the file at
    :param identifier: the data identifier
    :param data: the data to store
    :param length: the length of the data (defaults to -1: unknown)
    :param mimetype: the data mimetype
    :param tags: optional metadata describing the file
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the data was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remote_path: Path = Path(basepath) / identifier
        obj_name: str = remote_path.as_posix()

        # store the data
        bin_data: BinaryIO
        if isinstance(data, BinaryIO):
            bin_data = data
        else:
            bin_data = BytesIO(data) if isinstance(data, bytes) else \
                       BytesIO(bytes(data, "utf-8"))
            bin_data.seek(0)
        try:
            curr_client.put_object(bucket_name=bucket,
                                   object_name=obj_name,
                                   data=bin_data,
                                   length=length,
                                   content_type=mimetype,
                                   tags=__normalize_tags(tags))
            result = True
            _log(logger=logger,
                 stmt=(f"Stored {obj_name}, bucket {bucket}, "
                          f"content type {mimetype}, tags {tags}"))
        except Exception as e:
            _except_msg(errors=errors,
                        exception=e,
                        engine="minio",
                        logger=logger)
    return result


def data_retrieve(errors: list[str],
                  bucket: str,
                  basepath: str | Path,
                  identifier: str,
                  offset: int = 0,
                  length: int = 0,
                  client: Minio = None,
                  logger: Logger = None) -> bytes:
    """
    Retrieve data from the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the data from
    :param identifier: the data identifier
    :param offset: the start position within the data (in bytes, defaults to 0: data start)
    :param length: the length of the data to retrieve (in bytes, defaults to 0: to data finish)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the bytes retrieved, or 'None' if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remote_path: Path = Path(basepath) / identifier
        obj_name: str = remote_path.as_posix()

        # retrieve the data
        try:
            response: HTTPResponse = curr_client.get_object(bucket_name=bucket,
                                                            object_name=obj_name,
                                                            offset=offset,
                                                            length=length)
            result = response.data
            _log(logger=logger,
                 stmt=f"Retrieved {obj_name}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _except_msg(errors=errors,
                            exception=e,
                            engine="minio",
                            logger=logger)
    return result


def file_store(errors: list[str],
               bucket: str,
               basepath: str | Path,
               identifier: str,
               filepath: Path | str,
               mimetype: str,
               tags: dict[str, str] = None,
               client: Minio = None,
               logger: Logger = None) -> bool:
    """
    Store a file at the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to store the file at
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata describing the file
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the file was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remote_path: Path = Path(basepath) / identifier
        obj_name: str = remote_path.as_posix()

        # store the file
        try:
            curr_client.fput_object(bucket_name=bucket,
                                    object_name=obj_name,
                                    file_path=filepath,
                                    content_type=mimetype,
                                    tags=__normalize_tags(tags))
            result = True
            _log(logger=logger,
                 stmt=(f"Stored {obj_name}, bucket {bucket}, "
                          f"content type {mimetype}, tags {tags}"))
        except Exception as e:
            _except_msg(errors=errors,
                        exception=e,
                        engine="minio",
                        logger=logger)
    return result


def file_retrieve(errors: list[str],
                  bucket: str,
                  basepath: str | Path,
                  identifier: str,
                  filepath: Path | str,
                  client: Minio = None,
                  logger: Logger = None) -> Any:
    """
    Retrieve a file from the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the file from
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information about the file retrieved, or 'None' if error or file not found
    """
    # initialize the return variable
    result: Any = None

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            result = curr_client.fget_object(bucket_name=bucket,
                                             object_name=f"{remotepath}",
                                             file_path=filepath)
            _log(logger=logger,
                 stmt=f"Retrieved {remotepath}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _except_msg(errors=errors,
                            exception=e,
                            engine="minio",
                            logger=logger)
    return result


def object_store(errors: list[str],
                 bucket: str,
                 basepath: str | Path,
                 identifier: str,
                 obj: Any,
                 tags: dict[str, str] = None,
                 client: Minio = None,
                 logger: Logger = None) -> bool:
    """
    Store an object at the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to store the object at
    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadata describing the object
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the object was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # proceed, if the MinIO client was obtained
    if curr_client:
        # serialize the object into a file
        temp_folder: Path = _get_param("minio", "temp-folder")
        filepath: Path = temp_folder / f"{uuid.uuid4()}.pickle"
        with filepath.open("wb") as f:
            pickle.dump(obj, f)

        # store the file
        op_errors: list[str] = []
        file_store(errors=op_errors,
                   bucket=bucket,
                   basepath=basepath,
                   identifier=identifier,
                   filepath=filepath,
                   mimetype="application/octet-stream",
                   tags=tags,
                   client=curr_client,
                   logger=logger)
        # errors ?
        if op_errors:
            # yes, report them
            errors.extend(op_errors)
            storage: str = "Unable to store"
        else:
            # no, remove the file from the file system
            result = True
            filepath.unlink()
            storage: str = "Stored "

        remotepath: Path = Path(basepath) / identifier
        _log(logger=logger,
             stmt=f"{storage} {remotepath}, bucket {bucket}")

    return result


def object_retrieve(errors: list[str],
                    bucket: str,
                    basepath: str | Path,
                    identifier: str,
                    client: Minio = None,
                    logger: Logger = None) -> Any:
    """
    Retrieve an object from the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the object retrieved, or 'None' if error or object not found
    """
    # initialize the return variable
    result: Any = None

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # proceed, if the MinIO client was obtained
    if curr_client:
        # retrieve the file containg the serialized object
        temp_folder: Path = _get_param("minio", "temp-folder")
        filepath: Path = temp_folder / f"{uuid.uuid4()}.pickle"
        stat: Any = file_retrieve(errors=errors,
                                  bucket=bucket,
                                  basepath=basepath,
                                  identifier=identifier,
                                  filepath=filepath,
                                  client=curr_client,
                                  logger=logger)
        # was the file retrieved ?
        if stat:
            # yes, umarshall the corresponding object
            with filepath.open("rb") as f:
                result = pickle.load(f)
            filepath.unlink()

        retrieval: str = "Retrieved" if result else "Unable to retrieve"
        remotepath: Path = Path(basepath) / identifier
        _log(logger=logger,
             stmt=f"{retrieval} {remotepath}, bucket {bucket}")

    return result


def item_exists(errors: list[str],
                bucket: str,
                basepath: str | Path,
                identifier: str | None,
                client: Minio = None,
                logger: Logger = None) -> bool:
    """
    Determine if a given object exists in the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying where to locate the object
    :param identifier: optional object identifier
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the object was found, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # proceed, if the MinIO client eas obtained
    if curr_client:
        # was the identifier provided ?
        if not identifier:
            # no, object is a folder
            objs: Iterator = items_list(errors=errors,
                                        bucket=bucket,
                                        basepath=basepath,
                                        recursive=False,
                                        client=curr_client,
                                        logger=logger)
            result = next(objs, None) is None

        # verify the status of the object
        elif item_stat(errors=errors,
                       bucket=bucket,
                       basepath=basepath,
                       identifier=identifier,
                       client=curr_client,
                       logger=logger):
            result = True

        remotepath: Path = Path(basepath) / identifier
        existence: str = "exists" if result else "do not exist"
        _log(logger=logger,
             stmt=f"Object {remotepath}, bucket {bucket}, {existence}")

    return result


def item_stat(errors: list[str],
              bucket: str,
              basepath: str | Path,
              identifier: str,
              client: Minio = None,
              logger: Logger = None) -> MinioObject:
    """
    Retrieve and return the information about an item in the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying where to locate the object
    :param identifier: the object identifier
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: metadata and information about the item, or 'None' if error or item not found
    """
    # initialize the return variable
    result: MinioObject | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            result = curr_client.stat_object(bucket_name=bucket,
                                             object_name=f"{remotepath}")
            _log(logger=logger,
                 stmt=f"Stat'ed {remotepath}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _except_msg(errors=errors,
                            exception=e,
                            engine="minio",
                            logger=logger)
    return result


def item_remove(errors: list[str],
                bucket: str,
                basepath: str | Path,
                identifier: str = None,
                client: Minio = None,
                logger: Logger = None) -> bool:
    """
    Remove an item from the *MinIO* store.

    If *identifier* is not provided, then the folder *basepath* is deleted

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to delete the object at
    :param identifier: optional object identifier
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the item or folder was deleted or did not exist, 'False' if an error ocurred
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # proceed, if the MinIO client was obtained
    if curr_client:
        # was the identifier provided ?
        if identifier is None:
            # no, remove the folder
            result = _folder_delete(errors=errors,
                                    bucket=bucket,
                                    basepath=basepath,
                                    client=curr_client,
                                    logger=logger)
        else:
            # yes, remove the object
            remotepath: Path = Path(basepath) / identifier
            try:
                curr_client.remove_object(bucket_name=bucket,
                                          object_name=f"{remotepath}")
                result = True
                _log(logger=logger,
                     stmt=f"Deleted {remotepath}, bucket {bucket}")
            except Exception as e:
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    _except_msg(errors=errors,
                                exception=e,
                                engine="minio",
                                logger=logger)
    return result


def items_list(errors: list[str],
               bucket: str,
               basepath: str | Path,
               recursive: bool = False,
               client: Minio = None,
               logger: Logger = None) -> Iterator:
    """
    Retrieve and return an iterator into the list of items at *basepath*, in the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to iterate from
    :param recursive: whether the location is iterated recursively
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the iterator into the list of items, or 'None' if error or folder not found
    """
    # initialize the return variable
    result: Iterator | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        try:
            result = curr_client.list_objects(bucket_name=bucket,
                                              prefix=basepath,
                                              recursive=recursive)
            _log(logger=logger,
                 stmt=f"Listed {basepath}, bucket {bucket}")
        except Exception as e:
            _except_msg(errors=errors,
                        exception=e,
                        engine="minio",
                        logger=logger)
    return result


def tags_retrieve(errors: list[str],
                  bucket: str,
                  basepath: str | Path,
                  identifier: str,
                  client: Minio = None,
                  logger: Logger = None) -> dict[str, str]:
    """
    Retrieve and return the metadata information for an item in the *MinIO* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata about the item, or 'None' if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or get_client(errors=errors,
                                              logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            tags: Tags = curr_client.get_object_tags(bucket_name=bucket,
                                                     object_name=f"{remotepath}")
            if tags and len(tags) > 0:
                result = {}
                for key, value in tags.items():
                    result[key] = str_from_hex(value)
            _log(logger=logger,
                 stmt=f"Retrieved {remotepath}, bucket {bucket}, tags {result}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _except_msg(errors=errors,
                            exception=e,
                            engine="minio",
                            logger=logger)

    return result


def _folder_delete(errors: list[str],
                   bucket: str,
                   basepath: str | Path,
                   client: Minio,
                   logger: Logger = None) -> bool:
    """
    Traverse the folders recursively, removing its objects.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to delete the objects at
    :param client: the MinIO client object
    :param logger: optional logger
    """
    # initialize the return variable
    result: bool = True

    # obtain the list of entries in the given folder
    objs: Iterator = items_list(errors=errors,
                                bucket=bucket,
                                basepath=basepath,
                                recursive=True,
                                logger=logger) or []
    # traverse the list
    for obj in objs:
        try:
            client.remove_object(bucket_name=bucket,
                                 object_name=obj.object_name)
            _log(logger=logger,
                 stmt=f"Removed folder {basepath}, bucket {bucket}")
        except Exception as e:
            # SANITY CHECK: in case of concurrent exclusion
            # ruff: noqa: PERF203
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                result = False
                _except_msg(errors=errors,
                            exception=e,
                            engine="minio",
                            logger=logger)
    return result


def __normalize_tags(tags: dict[str, str]) -> Tags:

    # initialize return variable
    result: Tags | None

    # have tags been defined ?
    if tags:
        # yes, process them
        result = Tags(for_object=True)
        for key, value in tags.items():
            # normalize key, by removing all diacritics,
            # and convert 'value' to its hex representation
            result[unidecode(key)] = str_to_hex(value)
    else:
        result = None

    return result
