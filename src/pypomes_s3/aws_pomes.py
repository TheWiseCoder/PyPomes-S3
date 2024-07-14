import pickle
import uuid
from boto3.session import Session
from botocore.client import BaseClient
from collections.abc import Iterator
from logging import Logger
from pathlib import Path
from typing import Any
from unidecode import unidecode

from .s3_common import (
    _s3_get_param, _s3_get_params, _s3_except_msg, _s3_log
)


def access(errors: list[str],
           logger: Logger = None) -> BaseClient:
    """
    Obtain and return a *AWS* client object.

    :param errors: incidental error messages
    :param logger: optional logger
    :return: the S3 client object
    """
    # initialize the return variable
    result: BaseClient | None = None

    # retrieve the access parameters
    access_key, secret_key, region_name = _s3_get_params("aws")

    try:
        result = Session().client(service_name="s3",
                                  region_name=region_name,
                                  aws_access_key_id=access_key,
                                  aws_secret_access_key=secret_key)
    except Exception as e:
        _s3_except_msg(errors=errors,
                       exception=e,
                       engine="aws",
                       logger=logger)

    return result


def startup(errors: list[str],
            bucket: str,
            logger: Logger = None) -> bool:
    """
    Prepare the *AWS* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the AWS service is fully functional.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param logger: optional logger
    :return: True if service is fully functional
    """
    # initialize the return variable
    result: bool = False

    # obtain a AWS client
    client: BaseClient = access(errors=errors,
                                logger=logger)

    # was the AWS client obtained ?
    if client:
        # yes, proceed
        try:
            if not client.bucket_exists(bucket_name=bucket):
                client.make_bucket(bucket_name=bucket)
            result = True
            _s3_log(logger=logger,
                    stmt=f"Started AWS, bucket={bucket}")
        except Exception as e:
            _s3_except_msg(errors=errors,
                           exception=e,
                           engine="aws",
                           logger=logger)
    return result


def file_store(errors: list[str],
               bucket: str,
               basepath: str,
               identifier: str,
               filepath: Path | str,
               mimetype: str,
               tags: dict[str, Any] = None,
               client: BaseClient = None,
               logger: Logger = None) -> bool:
    """
    Store a file at the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to store the file at
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata describing the file
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the file was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # was the AWS client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        # have tags been defined ?
        if tags is None or len(tags) == 0:
            # no
            doc_tags = None
        else:
            # sim, store them
            doc_tags = {}
            for key, value in tags.items():
                # normalize text, by removing all diacritics
                doc_tags[key] = unidecode(value)
        # store the file
        try:
            curr_client.fput_object(bucket_name=bucket,
                                    object_name=f"{remotepath}",
                                    file_path=filepath,
                                    content_type=mimetype,
                                    tags=doc_tags)
            result = True
            _s3_log(logger=logger,
                    stmt=(f"Stored {remotepath}, bucket {bucket}, "
                          f"content type {mimetype}, tags {tags}"))
        except Exception as e:
            _s3_except_msg(errors=errors,
                           exception=e,
                           engine="aws",
                           logger=logger)
    return result


def file_retrieve(errors: list[str],
                  bucket: str,
                  basepath: str,
                  identifier: str,
                  filepath: Path | str,
                  client: BaseClient = None,
                  logger: Logger = None) -> Any:
    """
    Retrieve a file from the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the file from
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information about the file retrieved, or 'None' if an error ocurred
    """
    # initialize the return variable
    result: Any = None

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # was the AWS client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            result = curr_client.fget_object(bucket_name=bucket,
                                             object_name=f"{remotepath}",
                                             file_path=filepath)
            _s3_log(logger=logger,
                    stmt=f"Retrieved {remotepath}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _s3_except_msg(errors=errors,
                               exception=e,
                               engine="aws",
                               logger=logger)
    return result


def object_store(errors: list[str],
                 bucket: str,
                 basepath: str,
                 identifier: str,
                 obj: Any,
                 tags: dict[str, Any] = None,
                 client: BaseClient = None,
                 logger: Logger = None) -> bool:
    """
    Store an object at the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to store the object at
    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadata describing the object
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the object was successfully stored, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # proceed, if the AWS client was obtained
    if curr_client:
        # serialize the object into a file
        temp_folder: Path = _s3_get_param("minio", "temp-folder")
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
        _s3_log(logger=logger,
                stmt=f"{storage} {remotepath}, bucket {bucket}")

    return result


def object_retrieve(errors: list[str],
                    bucket: str,
                    basepath: str,
                    identifier: str,
                    client: BaseClient = None,
                    logger: Logger = None) -> Any:
    """
    Retrieve an object from the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the object retrieved, or 'None' if an error ocurred
    """
    # initialize the return variable
    result: Any = None

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # proceed, if the AWS client was obtained
    if curr_client:
        # retrieve the file containg the serialized object
        temp_folder: Path = _s3_get_param("minio", "temp-folder")
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
        _s3_log(logger=logger,
                stmt=f"{retrieval} {remotepath}, bucket {bucket}")

    return result


def item_exists(errors: list[str],
                bucket: str,
                basepath: str,
                identifier: str | None,
                client: BaseClient = None,
                logger: Logger = None) -> bool:
    """
    Determine if a given object exists in the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying where to locate the object
    :param identifier: optional object identifier
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the object was found, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # proceed, if the AWS client eas obtained
    if curr_client:
        # was the identifier provided ?
        if identifier is None:
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
        _s3_log(logger=logger,
                stmt=f"Object {remotepath}, bucket {bucket}, {existence}")

    return result


def item_stat(errors: list[str],
              bucket: str,
              basepath: str,
              identifier: str,
              client: BaseClient = None,
              logger: Logger = None) -> dict:
    """
    Retrieve and return the information about an object in the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying where to locate the object
    :param identifier: the object identifier
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: metadata and information about the object, or 'None' if an error ocurred
    """
    # initialize the return variable
    result: dict | None = None

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # was the AWS client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            result = curr_client.stat_object(bucket_name=bucket,
                                             object_name=f"{remotepath}")
            _s3_log(logger=logger,
                    stmt=f"Stat'ed {remotepath}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _s3_except_msg(errors=errors,
                               exception=e,
                               engine="aws",
                               logger=logger)
    return result


def item_remove(errors: list[str],
                bucket: str,
                basepath: str,
                identifier: str = None,
                client: BaseClient = None,
                logger: Logger = None) -> bool:
    """
    Remove an object from the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the object's remote location
    :param identifier: optional object identifier
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: 'True' if the object was successfully removed, 'False' otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # proceed, if the AWS client was obtained
    if curr_client:
        # was the identifier provided ?
        if identifier is None:
            # no, remove the folder
            _folder_delete(errors=errors,
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
                _s3_log(logger=logger,
                        stmt=f"Deleted {remotepath}, bucket {bucket}")
            except Exception as e:
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    _s3_except_msg(errors=errors,
                                   exception=e,
                                   engine="aws",
                                   logger=logger)
    return result


def tags_retrieve(errors: list[str],
                  bucket: str,
                  basepath: str,
                  identifier: str,
                  client: BaseClient = None,
                  logger: Logger = None) -> dict[str, Any]:
    """
    Retrieve and return the metadata information for an object in the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata about the object, or 'None' if an error ocurred
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # was the AWS client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            tags: dict = curr_client.get_object_tags(bucket_name=bucket,
                                                     object_name=f"{remotepath}")
            if tags and len(tags) > 0:
                result = {}
                for key, value in tags.items():
                    result[key] = value
            _s3_log(logger=logger,
                    stmt=f"Retrieved {remotepath}, bucket {bucket}, tags {result}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                _s3_except_msg(errors=errors,
                               exception=e,
                               engine="aws",
                               logger=logger)

    return result


def items_list(errors: list[str],
               bucket: str,
               basepath: str,
               recursive: bool = False,
               client: BaseClient = None,
               logger: Logger = None) -> Iterator:
    """
    Retrieve and return an iterator into the list of objects at *basepath*, in the *AWS* store.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to iterate from
    :param recursive: whether the location is iterated recursively
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the iterator into the list of objects, or 'None' if the folder does not exist
    """
    # initialize the return variable
    result: Iterator | None = None

    # make sure to have a AWS client
    curr_client: BaseClient = client or access(errors=errors,
                                               logger=logger)
    # was the AWS client obtained ?
    if curr_client:
        # yes, proceed
        try:
            result = curr_client.list_objects(bucket_name=bucket,
                                              prefix=basepath,
                                              recursive=recursive)
            _s3_log(logger=logger,
                    stmt=f"Listed {basepath}, bucket {bucket}")
        except Exception as e:
            _s3_except_msg(errors=errors,
                           exception=e,
                           engine="aws",
                           logger=logger)

    return result


def _folder_delete(errors: list[str],
                   bucket: str,
                   basepath: str,
                   client: BaseClient,
                   logger: Logger = None) -> None:
    """
    Traverse the folders recursively, removing its objects.

    :param errors: incidental error messages
    :param bucket: the bucket to use
    :param basepath: the path specifying the location to delete the objects at
    :param client: the MinIO client object
    :param logger: optional logger
    """
    # obtain the list of entries in the given folder
    objs: Iterator = items_list(errors=errors,
                                bucket=bucket,
                                basepath=basepath,
                                recursive=True,
                                logger=logger)
    # was the list obtained ?
    if objs:
        # yes, proceed
        for obj in objs:
            try:
                client.remove_object(bucket_name=bucket,
                                     object_name=obj.object_name)
                _s3_log(logger=logger,
                        stmt=f"Removed folder {basepath}, bucket {bucket}")
            except Exception as e:
                # SANITY CHECK: in case of concurrent exclusion
                # ruff: noqa: PERF203
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    _s3_except_msg(errors=errors,
                                   exception=e,
                                   engine="aws",
                                   logger=logger)
