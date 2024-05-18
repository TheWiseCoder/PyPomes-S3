import pickle
import uuid
from collections.abc import Iterator
from logging import Logger
from minio import Minio
from minio.datatypes import Object as MinioObject
from minio.commonconfig import Tags
from pathlib import Path
from pypomes_core import (
    APP_PREFIX, TEMP_DIR,
    env_get_bool, env_get_str, env_get_path
)
from typing import Final
from unidecode import unidecode

MINIO_BUCKET_NAME: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_BUCKET_URL")
MINIO_ENDPOINT_URL: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_ENDPOINT_URL")
MINIO_ACCESS_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_ACCESS_KEY")
MINIO_SECRET_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_SECRET_KEY")
MINIO_SECURE_ACCESS: Final[bool] = env_get_bool(f"{APP_PREFIX}_MINIO_SECURE_ACCESS")
MINIO_TEMP_PATH: Final[Path] = env_get_path(f"{APP_PREFIX}_MINIO_TEMP_PATH", TEMP_DIR)


def minio_access(errors: list[str],
                 logger: Logger = None) -> Minio:
    """
    Obtain and return a *MinIO* client object.

    :param errors: incidental error messages
    :param logger: optional logger
    :return: the MinIO client object
    """
    # initialize the return variable
    result: Minio | None = None

    # obtain the MinIO client
    try:
        result = Minio(endpoint=MINIO_ENDPOINT_URL,
                       access_key=MINIO_ACCESS_KEY,
                       secret_key=MINIO_SECRET_KEY,
                       secure=MINIO_SECURE_ACCESS)
        if logger:
            logger.debug("Minio client created")

    except Exception as e:
        __minio_except_msg(errors=errors,
                           exception=e,
                           logger=logger)

    return result


def minio_setup(errors: list[str],
                bucket: str = MINIO_BUCKET_NAME,
                client: Minio = None,
                logger: Logger = None) -> bool:
    """
    Prepare the *MinIO* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the MinIo service is fully functional.

    :param errors: incidental error messages
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if service is fully functional
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        try:
            if not curr_client.bucket_exists(bucket_name=bucket):
                curr_client.make_bucket(bucket_name=bucket)
            result = True
            if logger:
                logger.debug(f"Setup MinIO, endpoint={MINIO_ENDPOINT_URL}, bucket={bucket}, "
                             f"access key={MINIO_ACCESS_KEY}, secure={MINIO_SECURE_ACCESS}")
        except Exception as e:
            __minio_except_msg(errors=errors,
                               exception=e,
                               logger=logger)

    return result


def minio_file_store(errors: list[str],
                     basepath: Path | str,
                     identifier: str,
                     filepath: Path | str,
                     mimetype: str,
                     tags: dict = None,
                     bucket: str = MINIO_BUCKET_NAME,
                     client: Minio = None,
                     logger: Logger = None) -> None:
    """
    Store a file at the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the file at
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata describing the file
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    """
    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        # have tags been defined ?
        if tags is None or len(tags) == 0:
            # no
            doc_tags = None
        else:
            # sim, store them
            doc_tags = Tags(for_object=True)
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
            if logger:
                logger.debug(f"Stored {remotepath}, "
                             f"content type {mimetype}, tags {tags}, bucket {bucket}")
        except Exception as e:
            __minio_except_msg(errors=errors,
                               exception=e,
                               logger=logger)


def minio_file_retrieve(errors: list[str],
                        basepath: Path | str,
                        identifier: str,
                        filepath: Path | str,
                        bucket: str = MINIO_BUCKET_NAME,
                        client: Minio = None,
                        logger: Logger = None) -> any:
    """
    Retrieve a file from the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the file from
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information about the file retrieved
    """
    # initialize the return variable
    result: any = None

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            result = curr_client.fget_object(bucket_name=bucket,
                                             object_name=f"{remotepath}",
                                             file_path=filepath)
            if logger:
                logger.debug(f"Retrieved {remotepath}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                __minio_except_msg(errors=errors,
                                   exception=e,
                                   logger=logger)

    return result


def minio_object_exists(errors: list[str],
                        basepath: Path | str,
                        identifier: str = None,
                        bucket: str = MINIO_BUCKET_NAME,
                        client: Minio = None,
                        logger: Logger = None) -> bool:
    """
    Determine if a given object exists in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to locate the object at
    :param identifier: the object identifier
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: True if the object was found
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # proceed, if the MinIO client eas obtained
    if curr_client:
        # was the identifier provided ?
        if identifier is None:
            # no, object is a folder
            objs: Iterator = minio_objects_list(errors=errors,
                                                basepath=basepath,
                                                recursive=False,
                                                bucket=bucket,
                                                client=curr_client,
                                                logger=logger)
            for _ in objs:
                result = True
                break
        # verify the status of the object
        elif minio_object_stat(errors=errors,
                               basepath=basepath,
                               identifier=identifier,
                               bucket=bucket,
                               client=curr_client,
                               logger=logger):
            result = True
        if logger:
            remotepath: Path = Path(basepath) / identifier
            existence: str = "exists" if result else "do not exist"
            logger.debug(f"Object {remotepath}, bucket {bucket}, {existence}")

    return result


def minio_object_stat(errors: list[str],
                      basepath: Path | str,
                      identifier: str,
                      bucket: str = MINIO_BUCKET_NAME,
                      client: Minio = None,
                      logger: Logger = None) -> MinioObject:
    """
    Retrieve and return the information about an object in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying where to locate the object
    :param identifier: the object identifier
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: metadata and information about the object
    """
    # initialize the return variable
    result: MinioObject | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            result = curr_client.stat_object(bucket_name=bucket,
                                             object_name=f"{remotepath}")
            if logger:
                logger.debug(f"Stat'ed {remotepath}, bucket {bucket}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                __minio_except_msg(errors=errors,
                                   exception=e,
                                   logger=logger)

    return result


def minio_object_store(errors: list[str],
                       basepath: Path | str,
                       identifier: str,
                       obj: any,
                       tags: dict = None,
                       bucket: str = MINIO_BUCKET_NAME,
                       client: Minio = None,
                       logger: Logger = None) -> None:
    """
    Store an object at the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the object at
    :param identifier: the object identifier
    :param obj: object to be stored
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :param tags: optional metadata describing the object
    """
    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # proceed, if the MinIO client was obtained
    if curr_client:
        # serialize the object into a file
        filepath: Path = Path(MINIO_TEMP_PATH) / f"{uuid.uuid4()}.pickle"
        with filepath.open("wb") as f:
            pickle.dump(obj, f)

        # store the file
        op_errors: list[str] = []
        minio_file_store(errors=op_errors,
                         basepath=basepath,
                         identifier=identifier,
                         filepath=filepath,
                         mimetype="application/octet-stream",
                         tags=tags,
                         bucket=bucket,
                         client=curr_client,
                         logger=logger)

        # errors ?
        if op_errors:
            # yes, report them
            errors.extend(op_errors)
            storage: str = "Unable to store"
        else:
            # no, remove the file from the file system
            filepath.unlink()
            storage: str = "Stored "

        if logger:
            remotepath: Path = Path(basepath) / identifier
            logger.debug(f"{storage} {remotepath}, bucket {bucket}")


def minio_object_retrieve(errors: list[str],
                          basepath: Path,
                          identifier: str,
                          bucket: str = MINIO_BUCKET_NAME,
                          client: Minio = None,
                          logger: Logger = None) -> any:
    """
    Retrieve an object from the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the object retrieved
    """
    # initialize the return variable
    result: any = None

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # proceed, if the MinIO client was obtained
    if curr_client:
        # retrieve the file containg the serialized object
        filepath: Path = Path(MINIO_TEMP_PATH) / f"{uuid.uuid4()}.pickle"
        stat: any = minio_file_retrieve(errors=errors,
                                        basepath=basepath,
                                        identifier=identifier,
                                        filepath=filepath,
                                        bucket=bucket,
                                        client=curr_client,
                                        logger=logger)

        # was the file retrieved ?
        if stat:
            # yes, umarshall the corresponding object
            with filepath.open("rb") as f:
                result = pickle.load(f)
            filepath.unlink()

        if logger:
            retrieval: str = "Retrieved" if result else "Unable to retrieve"
            remotepath: Path = Path(basepath) / identifier
            logger.debug(f"{retrieval} {remotepath}, bucket {bucket}")

    return result


def minio_object_delete(errors: list[str],
                        basepath: str,
                        identifier: str = None,
                        bucket: str = MINIO_BUCKET_NAME,
                        client: Minio = None,
                        logger: Logger = None) -> None:
    """
    Remove an object from the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    """
    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # proceed, if the MinIO client was obtained
    if curr_client:
        # was the identifier provided ?
        if identifier is None:
            # no, remove the folder
            __minio_folder_delete(errors=errors,
                                  client=curr_client,
                                  basepath=basepath,
                                  bucket=bucket,
                                  logger=logger)
        else:
            # yes, remove the object
            remotepath: Path = Path(basepath) / identifier
            try:
                curr_client.remove_object(bucket_name=bucket,
                                          object_name=f"{remotepath}")
                if logger:
                    logger.debug(f"Deleted {remotepath}, bucket {bucket}")
            except Exception as e:
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    __minio_except_msg(errors=errors,
                                       exception=e,
                                       logger=logger)


# recupera as tags do objeto
def minio_object_tags_retrieve(errors: list[str],
                               basepath: str,
                               identifier: str,
                               bucket: str = MINIO_BUCKET_NAME,
                               client: Minio = None,
                               logger: Logger = None) -> dict:
    """
    Retrieve and return the metadata information for an object in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata about the object
    """
    # initialize the return variable
    result: dict | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        remotepath: Path = Path(basepath) / identifier
        try:
            tags: Tags = curr_client.get_object_tags(bucket_name=bucket,
                                                     object_name=f"{remotepath}")
            if tags is not None and len(tags) > 0:
                result = {}
                for key, value in tags.items():
                    result[key] = value
            if logger:
                logger.debug(f"Retrieved {remotepath}, bucket {bucket}, tags {result}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                __minio_except_msg(errors=errors,
                                   exception=e,
                                   logger=logger)

    return result


def minio_objects_list(errors: list[str],
                       basepath: str,
                       recursive: bool = False,
                       bucket: str = MINIO_BUCKET_NAME,
                       client: Minio = None,
                       logger: Logger = None) -> Iterator:
    """
    Retrieve and return an iterator into the list of objects at *basepath*, in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to iterate from
    :param recursive: whether the location is iterated recursively
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param client: optional MinIO client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the iterator into the list of objects, 'None' if the folder does not exist
    """
    # initialize the return variable
    result: Iterator | None = None

    # make sure to have a MinIO client
    curr_client: Minio = client or minio_access(errors=errors,
                                                logger=logger)
    # was the MinIO client obtained ?
    if curr_client:
        # yes, proceed
        try:
            result = curr_client.list_objects(bucket_name=bucket,
                                              prefix=basepath,
                                              recursive=recursive)
            if logger:
                logger.debug(f"Listed {basepath}, bucket {bucket}")
        except Exception as e:
            __minio_except_msg(errors=errors,
                               exception=e,
                               logger=logger)

    return result


def __minio_folder_delete(errors: list[str],
                          client: Minio,
                          basepath: str,
                          bucket: str = MINIO_BUCKET_NAME,
                          logger: Logger = None) -> None:
    """
    Traverse the folders recursively, removing its objects.

    :param errors: incidental error messages
    :param client: the MinIO client object
    :param basepath: the path specifying the location to delete the objects at
    :param bucket: the bucket to use (defaults to MINIO_BUCKET)
    :param logger: optional logger
    """
    # obtain the list of entries in the given folder
    objs: Iterator = minio_objects_list(errors=errors,
                                        basepath=basepath,
                                        recursive=True,
                                        bucket=bucket,
                                        logger=logger)
    # was the list obtained ?
    if objs:
        # yes, proceed
        for obj in objs:
            try:
                client.remove_object(bucket_name=bucket,
                                     object_name=obj.object_name)
            except Exception as e:
                # SANITY CHECK: in case of concurrent exclusion
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    __minio_except_msg(errors=errors,
                                       exception=e,
                                       logger=logger)
        if logger:
            logger.debug(msg=f"Removed folder {basepath}, bucket {bucket}")


def __minio_except_msg(errors: list[str],
                       exception: Exception,
                       logger: Logger) -> None:
    """
    Format and return an error message from *exception*.

    :param errors: incidental error messages
    :param exception: the reference exception
    :param logger: optional logger
    :return: the error message
    """
    # interaction with MinIO raised the exception "<class 'exception_class'>"
    cls: str = str(exception.__class__)
    exc_msg: str = f"{cls[7:-1]} - {exception}"
    err_msg: str = f"Error accessing the object storer: {exc_msg}"
    if errors:
        errors.append(err_msg)
    if logger:
        logger.error(msg=err_msg)
