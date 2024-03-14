import os
import pickle
import uuid
from collections.abc import Iterator
from minio import Minio
from minio.datatypes import Object as MinioObject
from minio.commonconfig import Tags
from pathlib import Path
from pypomes_core import APP_PREFIX, TEMP_DIR, env_get_bool, env_get_str, env_get_path
from typing import Final
from unidecode import unidecode

MINIO_BUCKET: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_BUCKET")
MINIO_HOST: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_HOST")
MINIO_ACCESS_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_ACCESS_KEY")
MINIO_SECRET_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_SECRET_KEY")
MINIO_SECURE_ACCESS: Final[bool] = env_get_bool(F"{APP_PREFIX}_MINIO_SECURE_ACCESS")
MINIO_TEMP_PATH: Final[Path] = env_get_path(f"{APP_PREFIX}_MINIO_TEMP_PATH", TEMP_DIR)


def minio_setup(errors: list[str]) -> bool:
    """
    Prepare the *MinIO* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the MinIo service is fully functional.

    :param errors: incidental error messages
    :return: True if service is fully functional
    """
    # initialize the return variable
    result: bool = True

    try:
        # retrieve the MinIO client
        minio_client = Minio(endpoint=MINIO_HOST,
                             access_key=MINIO_ACCESS_KEY,
                             secret_key=MINIO_SECRET_KEY,
                             secure=MINIO_SECURE_ACCESS)

        # build the bucket, if needed
        if not minio_client.bucket_exists(bucket_name=MINIO_BUCKET):
            minio_client.make_bucket(bucket_name=MINIO_BUCKET)

    except Exception as e:
        result = False
        errors.append(__minio_except_msg(e))

    return result


def minio_access(errors: list[str]) -> Minio:
    """
    Obtain and return the *MinIO* client object.

    :param errors: incidental error messages
    :return: the MinIO client object
    """
    # initialize the return variable
    result: Minio | None = None

    # retrieve the MinIO client
    try:
        result = Minio(endpoint=MINIO_HOST,
                       access_key=MINIO_ACCESS_KEY,
                       secret_key=MINIO_SECRET_KEY,
                       secure=MINIO_SECURE_ACCESS)

    except Exception as e:
        errors.append(__minio_except_msg(e))

    return result


def minio_file_store(errors: list[str], basepath: Path | str,
                     identifier: str, filepath: Path | str, mimetype: str, tags: dict = None) -> None:
    """
    Store a file at the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the file at
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata describing the file
    """
    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # was the MinIO client obtained ?
    if minio_client:
        # yes, store the file
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
        try:
            minio_client.fput_object(bucket_name=MINIO_BUCKET,
                                     object_name=f"{remotepath}",
                                     file_path=filepath,
                                     content_type=mimetype,
                                     tags=doc_tags)
        except Exception as e:
            errors.append(__minio_except_msg(e))


def minio_file_retrieve(errors: list[str], basepath: Path | str,
                        identifier: str, filepath: Path | str) -> any:
    """
    Retrieve a file from the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the file from
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :return: information about the file retrieved
    """
    # initialize the return variable
    result: any = None

    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # was the MinIO client obtained ?
    if minio_client:
        # yes, retrieve the file
        remotepath: Path = Path(basepath) / identifier
        try:
            result = minio_client.fget_object(bucket_name=MINIO_BUCKET,
                                              object_name=f"{remotepath}",
                                              file_path=filepath)
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                errors.append(__minio_except_msg(e))

    return result


def minio_object_exists(errors: list[str], basepath: Path | str, identifier: str = None) -> bool:
    """
    Determine if a given object exists in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to locate the object at
    :param identifier: the object identifier
    :return: True if the object was found
    """
    # initialize the return variable
    result: bool = False

    # was the identifier provided ?
    if identifier is None:
        # no, object is a folder
        objs: Iterator = minio_objects_list(errors, basepath)
        for _ in objs:
            result = True
            break
    # verify the status of the object
    elif minio_object_stat(errors, basepath, identifier):
        result = True

    return result


def minio_object_stat(errors: list[str], basepath: Path | str, identifier: str) -> MinioObject:
    """
    Retrieve and return the information about an object in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying where to locate the object
    :param identifier: the object identifier
    :return: metadata and information about the object
    """
    # initialize the return variable
    result: MinioObject | None = None

    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # was the MinIO client obtained ?
    if minio_client:
        # yes, retrieve the object's information
        remotepath: Path = Path(basepath) / identifier
        try:
            result = minio_client.stat_object(bucket_name=MINIO_BUCKET,
                                              object_name=f"{remotepath}")
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                errors.append(__minio_except_msg(e))

    return result


def minio_object_store(errors: list[str], basepath: Path | str,
                       identifier: str, obj: any, tags: dict = None) -> None:
    """
    Store an object at the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to store the object at
    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadata describing the object
    """
    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # proceed, if the MinIO client was obtained
    if minio_client:

        # serialize the object into a file
        filepath: Path = Path(MINIO_TEMP_PATH) / f"{uuid.uuid4()}.pickle"
        with Path.open(filepath, "wb") as f:
            pickle.dump(obj, f)

        # store the file and remove it
        minio_file_store(errors, basepath, identifier, filepath, "application/octet-stream", tags)
        Path.unlink(filepath)


def minio_object_retrieve(errors: list[str], basepath: Path, identifier: str) -> any:
    """
    Retrieve an object from the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :return: the object retrieved
    """
    # initialize the return variable
    result: any = None

    # retrieve the file containg the serialized object
    filepath: Path = Path(MINIO_TEMP_PATH) / f"{uuid.uuid4()}.pickle"
    stat: any = minio_file_retrieve(errors, basepath, identifier, filepath)

    # was the file retrieved ?
    if stat:
        # yes, umarshall the corresponding object
        with Path.open(filepath, "rb") as f:
            result = pickle.load(f)
        Path.unlink(filepath)

    return result


def minio_object_delete(errors: list[str], basepath: str, identifier: str = None) -> None:
    """
    Remove an object from the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    """
    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # proceed, if the MinIO client was obtained
    if minio_client:
        # was the identifier provided ?
        if identifier is None:
            # no, remove the folder
            __minio_folder_delete(errors, minio_client, basepath)
        else:
            # yes, remove the object
            remotepath: str = os.path.join(basepath, identifier)
            try:
                minio_client.remove_object(bucket_name=MINIO_BUCKET,
                                           object_name=remotepath)
            except Exception as e:
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    errors.append(__minio_except_msg(e))


# recupera as tags do objeto
def minio_object_tags_retrieve(errors: list[str], basepath: str, identifier: str) -> dict:
    """
    Retrieve and return the metadata information for an object in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to retrieve the object from
    :param identifier: the object identifier
    :return: the metadata about the object
    """
    # initialize the return variable
    result: dict | None = None

    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # was the MinIO client obtained ?
    if minio_client:
        # yes, proceed
        remotepath: str = os.path.join(basepath, identifier)
        try:
            tags: Tags = minio_client.get_object_tags(bucket_name=MINIO_BUCKET,
                                                      object_name=remotepath)
            if tags is not None and len(tags) > 0:
                result = {}
                for key, value in tags.items():
                    result[key] = value
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                errors.append(__minio_except_msg(e))

    return result


# retorna a lista de objetos na pasta identificada pelo argumento - None se pasta não existe
def minio_objects_list(errors: list[str], basepath: str, recursive: bool = False) -> Iterator:
    """
    Retrieve and return an iterator into the list of objects at *basepath*, in the *MinIO* store.

    :param errors: incidental error messages
    :param basepath: the path specifying the location to iterate from
    :param recursive: whether the location is iterated recursively
    :return: the iterator into the list of objects
    """
    # initialize the return variable
    result: any = None

    # obtain the MinIO client
    minio_client: Minio = minio_access(errors)

    # was the MinIO client obtained ?
    if minio_client:
        # yes, retrieve the iterator into the list of objects
        try:
            result = minio_client.list_objects(bucket_name=MINIO_BUCKET,
                                               prefix=basepath,
                                               recursive=recursive)
        except Exception as e:
            errors.append(__minio_except_msg(e))

    return result


def __minio_folder_delete(errors: list[str],  minio_client: Minio, basepath: str) -> None:
    """
    Traverse the folders recursively, removing its objects.

    :param errors: incidental error messages
    :param minio_client: the MinIO client object
    :param basepath: the path specifying the location to delete the objects at.
    """
    #
    try:
        objs: Iterator = minio_objects_list(errors, basepath, True)
        for obj in objs:
            try:
                minio_client.remove_object(bucket_name=MINIO_BUCKET,
                                           object_name=obj.object_name)
            except Exception as e:  # noqa: PERF203
                # SANITY CHECK: in case of concurrent exclusion
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    errors.append(__minio_except_msg(e))
    except Exception as e:
        errors.append(__minio_except_msg(e))


def __minio_except_msg(exception: Exception) -> str:
    """
    Format and return an error message from *exception*.

    :param exception: the reference exception
    :return: the error message
    """
    # interaction with MinIO raised the exception "<class 'exception_class'>"
    cls: str = str(exception.__class__)
    exc_msg: str = f"{cls[7:-1]} - {exception}"
    return f"Error accessing the object storer: {exc_msg}"
