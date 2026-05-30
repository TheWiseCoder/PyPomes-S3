import json
from datetime import timedelta
from google.api_core.exceptions import NotFound
from google.api_core.page_iterator import HTTPIterator
from google.cloud.storage import Client
from google.cloud.storage.blob import Blob
from google.cloud.storage.bucket import Bucket
from google.oauth2.service_account import Credentials
from io import BytesIO
from pathlib import Path
from pypomes_core import Mimetype, file_get_data
from typing import Any, BinaryIO

from .s3_common import (
    _S3_ACCESS_DATA, _S3_LOGGERS, S3Engine, S3Param,
    _get_param, _except_msg
)


def gcs_setup(*,
              bucket_name: str = None,
              project_id: str = None,
              credentials: dict[str, str] | BytesIO | Path | str | bytes = None,
              errors: list[str] = None) -> None:
    """
    Establish the parameters for access to *engine* of type *GCS*.

    *Google Cloud Storage* may use *Identity and Access Management* (IAM), instead of simple
    username/password strings.

    The nature of access *credentials* depends on its data type:
        - type *dict*: *credentials* is a Python dictionary
        - type *BytesIO*: *credentials* is a byte stream
        - type *Path*: *credentials* is a path to a file holding the data
        - type *bytes*: *credentials* holds the data (used as is)
        - type *str*: *credentials* holds the data (used as utf8-encoded)

    The *google.oauth2.service_account* package requires the credentials sampled below for authentication:
        - "type": "service_account",
        - "project_id": "my-gcp-project-id",
        - "private_key_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        - "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvgIBADANBhEFAASC+...\\n-----END PRIVATE KEY-----\\n",
        - "client_email": "my-service-account-name@my-gcp-project-id.iam.gserviceaccount.com",
        - "client_id": "12345678901234567890",
        - "auth_uri": "accounts.google.com",
        - "token_uri": "oauth2.googleapis.com",
        - "auth_provider_x509_cert_url": "www.googleapis.com",
        - "client_x509_cert_url": "www.googleapis.com"

    A credentials file for Google Cloud Storage is a standard *JSON* service account key file containing
    the data described above. The parameter *project_id* is required if *credentials* is not provided,
    otherwise it is ignored.

    :param bucket_name: the name of the default bucket
    :param project_id: optional project identification
    :param credentials: optional access credentials
    :param errors: incidental error messages (might be a non-empty list)
    """
    gcs_data: dict[str, Any] = _S3_ACCESS_DATA.get(S3Engine.GCS)
    if gcs_data:
        bucket_name = bucket_name or gcs_data.get(S3Param.BUCKET_NAME)
        project_id = project_id or gcs_data.get(S3Param.PROJECT_ID)
        credentials = credentials or gcs_data.get(S3Param.CREDENTIALS)

    if bucket_name and (project_id or credentials):
        # initilize the GCS parameters
        if credentials:
            if not isinstance(credentials, dict):
                credentials_bytes: bytes = file_get_data(file_data=credentials)
                credentials = json.loads(s=credentials_bytes)
            project_id = credentials.get("project_id")
        _S3_ACCESS_DATA[S3Engine.GCS] = {
            S3Param.BUCKET_NAME: bucket_name,
            S3Param.PROJECT_ID: project_id,
            S3Param.CREDENTIALS: credentials
        }
    else:
        err_msg = "'bucket_name' and either 'credentials' or 'project_id' must be provided"
        if _S3_LOGGERS[S3Engine.GCS]:
            _S3_LOGGERS[S3Engine.GCS].error(msg=err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)


def get_client(errors: list[str] = None) -> Client | None:
    """
    Obtain and return a *GCS* client object.

    :param errors: incidental error messages (might be a non-empty list)
    :return: the *GCS* client object, or *None* if error
    """
    # initialize the return variable
    result: Client | None = None

    # obtain the GCS client
    project_id: str = _get_param(engine=S3Engine.GCS,
                                 param=S3Param.PROJECT_ID)
    credentials: dict[str, str] = _get_param(engine=S3Engine.GCS,
                                             param=S3Param.CREDENTIALS)
    try:
        if credentials:
            # use specific service account data
            gcs_credentials: Any = Credentials.from_service_account_info(info=credentials)
            result = Client(project=project_id,
                            credentials=gcs_credentials)
        else:
            result = Client(project=project_id)
        if _S3_LOGGERS[S3Engine.GCS]:
            _S3_LOGGERS[S3Engine.GCS].debug(msg="*GCS* client created")

    except Exception as e:
        msg: str = _except_msg(exception=e,
                               engine=S3Engine.GCS)
        if _S3_LOGGERS[S3Engine.GCS]:
            _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
        if isinstance(errors, list):
            errors.append(msg)

    return result


def startup(bucket: str,
            errors: list[str] = None) -> bool:
    """
    Prepare the *GCS* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the S3 service is fully functional.

    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if service is fully functional, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # obtain a client
    client: Client = get_client(errors=errors)
    if client:
        try:
            client.get_bucket(bucket_or_name=bucket)
            result = True
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Started GCS, bucket '{bucket}' asserted")
        except Exception as e1:
            # log the exception and try to create a bucket
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].warning(msg=_except_msg(exception=e1,
                                                                  engine=S3Engine.GCS))
            try:
                client.create_bucket(bucket_or_name=bucket)
                result = True
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Started GCS, bucket '{bucket}' created")
            except Exception as e2:
                msg = _except_msg(exception=e2,
                                  engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def data_retrieve(identifier: str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  data_range: tuple[int, int] = None,
                  client: Client = None,
                  errors: list[str] = None) -> bytes | None:
    """
    Retrieve data from the *GCS* store.

    :param identifier: the data identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to be retrieved
    :param data_range: the begin-end positions within the data (in bytes, defaults to *None* - all bytes)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the bytes retrieved, or *None* if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        # retrieve the data (GCS uses inclusive indices for partial download)
        from_byte: int = data_range[0] if data_range else None
        to_byte: int = data_range[1] - 1 if data_range else None
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)
            result = gcs_blob.download_as_bytes(start=from_byte,
                                                end=to_byte)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Retrieved '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            if not isinstance(e, NotFound):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def data_store(identifier: str,
               data: bytes | str | BinaryIO,
               length: int | None,
               prefix: str | Path = None,
               mimetype: Mimetype | str = Mimetype.BINARY,
               tags: dict[str, str] = None,
               bucket: str = None,
               client: Client = None,
               errors: list[str] = None) -> None:
    """
    Store *data* at the *GCS* store.

    In case *length* cannot be determined, it should be set to *None*.
    Note that *length* is the number of bytes of *data* to be stored. This might lead to error when storing
    strings. In Python, a standard string is a sequence of Unicode code points, not bytes, and thus:
      - *len(string)*: returns the number of characters (Unicode code points)
      - *len(string.encode('utf-8'))*: returns the number of bytes the string occupies when encoded

    :param identifier: the data identifier
    :param data: the data to store
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param length:  the length of the data
    :param prefix: optional path prefixing the item holding the data
    :param mimetype: the data mimetype, defaults to *BINARY*
    :param tags: optional metadata tags describing the file
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    """
    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        bin_data: BinaryIO
        if isinstance(data, BinaryIO):
            bin_data = data
        else:
            bin_data = BytesIO(data) if isinstance(data, bytes) else \
                       BytesIO(bytes(data, "utf-8"))
            bin_data.seek(0)

        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            if isinstance(mimetype, Mimetype):
                mimetype = mimetype.value
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)
            if tags:
                gcs_blob.metadata = tags

            gcs_blob.upload_from_file(file_obj=bin_data,
                                      size=length,
                                      content_type=mimetype)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=(f"Stored '{obj_key}', bucket '{bucket}', "
                                                     f"content type '{mimetype}', tags '{tags}'"))
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.GCS)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)


def file_retrieve(identifier: str,
                  filepath: Path | str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  client: Client = None,
                  errors: list[str] = None) -> bool | None:
    """
    Retrieve a file from the *GCS* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to retrieve as a file
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the file was retrieved, *False* otherwise, or *None* if error
    """
    # initialize the return variable
    result: bool | None = False

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            file_path: str = Path(filepath).as_posix()
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)
            gcs_blob.download_to_filename(filename=file_path)
            result = Path(filepath).exists()
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"{obj_key}', bucket '{bucket}', "
                                                    f"{'retrieved' if result else 'not retrieved'}")
        except Exception as e:
            if not isinstance(e, NotFound):
                result = None
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def file_store(identifier: str,
               filepath: Path | str,
               mimetype: Mimetype | str,
               bucket: str = None,
               prefix: str | Path = None,
               tags: dict[str, str] = None,
               client: Client = None,
               errors: list[str] = None) -> bool:
    """
    Store a file at the *GCS* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: optional path specifying where the file is
    :param mimetype: the file mimetype
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item holding the file data
    :param tags: optional metadata tags describing the file
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the file was successfully stored, *False* if error
    """
    # initialize the return variable
    result: bool = False

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        # store the file
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            file_path: str = Path(filepath).as_posix()
            if isinstance(mimetype, Mimetype):
                mimetype = mimetype.value
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)
            if tags:
                gcs_blob.metadata = tags

            gcs_blob.upload_from_filename(filename=file_path,
                                          content_type=mimetype)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Stored '{obj_key}', "
                                                    f"bucket '{bucket}', from '{file_path}', "
                                                    f"content type '{mimetype}', tags '{tags}'")
            result = True
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.GCS)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)
    return result


def item_get_info(identifier: str,
                  attributes: list[str],
                  prefix: str | Path = None,
                  bucket: str = None,
                  client: Client = None,
                  errors: list[str] = None) -> dict[str, Any] | None:
    """
    Retrieve information about an item in the *GCS* store.

    The complete information that can be returned is shown below. The parameter *attributes* must contain
    one or more of the attributes listed. Attributes named *metadata.<custom_metadata_i* are the custom
     metadata associated with the data. Please refer to the published *GCS* documentation for the meaning
     of any of these attributes.
      - 'name': the blob name,
      - 'mimetype': the mime type of the data,
      - 'size': the data length,
      - 'md5_hash': the blob's MD5 hash,
      - 'updated': the blob's last updated timestamp,
      - 'generation': the blob's generation attribute,
      - 'metageneration': the blob's metageneration attribute,
      - 'storage_class': the blob's storage class,
      - 'metadata.<custom_metadata_1>': 'string',
      - ...
      - 'metadata.<custom_metadata_n>': 'string'

    :param identifier: the item identifier
    :param attributes: the item's attributes to be returned
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: information about the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)

            # retrieve updated properties and metadata
            gcs_blob.reload()
            result = {}
            if "name" in attributes:
                result["name"] = gcs_blob.name
            if "mimetype" in attributes:
                result["mimetype"] = gcs_blob.content_type
            if "size" in attributes:
                result["size"] = gcs_blob.size
            if "md5_hash" in attributes:
                result["md5_hash"] = gcs_blob.md5_hash
            if "updated" in attributes:
                result["updated"] = gcs_blob.updated
            if "generation" in attributes:
                result["generation"] = gcs_blob.generation
            if "metageneration" in attributes:
                result["metageneration"] = gcs_blob.metageneration
            if "storage_class" in attributes:
                result["storage_class"] = gcs_blob.storage_class
            for key, value in (gcs_blob.metadata or {}).items():
                if f"metadata.{key}" in attributes:
                    result[key] = value

            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Got info for '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            if not isinstance(e, NotFound):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def item_get_tags(identifier: str,
                  prefix: str | Path = None,
                  bucket: str = None,
                  client: Client = None,
                  errors: list[str] = None) -> dict[str, str] | None:
    """
    Retrieve the existing custom metadata tags for an item in the *GCS* store.

    If item has no associated metadata tags, an empty *dict* is returned.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the metadata tags associated with the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)

            # retrieve updated metadata
            gcs_blob.reload()
            result = gcs_blob.metadata or {}

            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Got tags for '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            if not isinstance(e, NotFound):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def item_remove(identifier: str,
                prefix: str | Path = None,
                version: int | str = None,
                bucket: str = None,
                client: Client = None,
                errors: list[str] = None) -> bool | None:
    """
    Remove an item from the *GCS* store.

    If *version* is not specified, then only the item's current (latest) version is removed.

    If provided, *version* must be an integer, or a string oncoding an integer.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item to be removed
    :param version: optional version of the item to be removed (defaults to its current version)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the item was successfully removed, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = False

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        if prefix:
            path: Path = Path(prefix) / identifier
            obj_key: str = path.as_posix()
        else:
            obj_key: str = identifier

        # remove the item
        if isinstance(version, str):
            version = int(version)
        try:
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key,
                                             generation=version)
            gcs_blob.delete()
            result = True
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Deleted '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            if not isinstance(e, NotFound):
                result = None
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result


def items_get_info(attributes: list[str],
                   prefix: str | Path,
                   max_count: int = None,
                   start_after: str = None,
                   bucket: str = None,
                   client: Client = None,
                   errors: list[str] = None) -> list[dict[str, Any]] | None:
    """
    Recursively retrieve and return information on a list of items prefixed with *prefix*, in the *GCS* store.

    If *prefix* is not specified, then the bucket's root is used. If *max_count* is a positive integer,
    the number of items returned may be less, but not more, than its value, otherwise it is ignored, and
    all existing items in *prefix* are returned. Optionally, *start_after* identifies the item after which
    the listing must start, thus allowing for paginating the items retrieval operation.

    The complete information that can be returned is shown below. The parameter *attributes* must contain
    one or more of the attributes listed. Attributes named *metadata.<custom_metadata_i* are the custom
     metadata associated with the data. Please refer to the published *GCS* documentation for the meaning
     of any of these attributes.
      - 'name': the blob name (always returned),
      - 'content_type': the mime type of the data,
      - 'size': the data length,
      - 'md5_hash': the blob's MD5 hash,
      - 'updated': the blob's last updated timestamp,
      - 'generation': the blob's generation attribute,
      - 'metageneration': the blob's metageneration attribute,
      - 'storage_class': the blob's storage class,
      - 'metadata.<custom_metadata_1>': 'string',
      - ...
      - 'metadata.<custom_metadata_n>': 'string'

    :param attributes: the items' attributes to be returned
    :param prefix: path prefixing the items to be listed
    :param max_count: the maximum number of items to return (defaults to all items)
    :param start_after: optionally identifies the item after which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: information on a list of items in *prefix*, or *None* if error or *prefix* not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        # must terminate with '/', otherwise only the folder is considered
        path: str = Path(prefix).as_posix() + "/" if prefix else None
        if not isinstance(max_count, int) or \
           isinstance(max_count, bool) or max_count < 0:
            max_count = 0
        max_keys: int = max_count if 0 < max_count < 1000 else 1000
        fields: str = "items("
        for attr in attributes:
            if not attr.startswith("metadata."):
                fields += f",{attr}"
            elif "metadata" not in fields:
                fields += ",metadata"
        if ",name" not in fields:
            fields += ",name"
        fields = fields.replace("items(,", "items(") + "),nextPageToken"

        # retrieve the info
        try:
            items: list[dict[str, Any]] = []
            proceed: bool = True
            while proceed:
                # retrieve up to 1000 objects at a time
                reply: HTTPIterator = client.list_blobs(bucket_or_name=bucket,
                                                        max_results=max_keys,
                                                        page_token=start_after,
                                                        prefix=path,
                                                        delimiter="/",
                                                        fields=fields)
                proceed = False
                page = next(reply.pages)
                for gcs_blob in page:
                    item: dict[str, Any] = {"name": gcs_blob.name}
                    if "content_type" in attributes:
                        item["content_type"] = gcs_blob.content_type
                    if "size" in attributes:
                        item["size"] = gcs_blob.size
                    if "md5_hash" in attributes:
                        item["md5_hash"] = gcs_blob.md5_hash
                    if "updated" in attributes:
                        item["updated"] = gcs_blob.updated
                    if "generation" in attributes:
                        item["generation"] = gcs_blob.generation
                    if "metageneration" in attributes:
                        item["metageneration"] = gcs_blob.metageneration
                    if "storage_class" in attributes:
                        item["storage_class"] = gcs_blob.storage_class
                    for key, value in (gcs_blob.metadata or {}).items():
                        if f"metadata.{key}" in attributes:
                            result[key] = value
                    items.append(item)

                start_after = reply.next_page_token
                if start_after > 0:
                    max_keys = max_count - len(result) if 0 < max_count - len(result) < 1000 else 1000
                    proceed = True

            # save the items and log the results
            result = items
            if _S3_LOGGERS[S3Engine.GCS]:
                msg: str = f"Listed {len(result)} items in '{prefix}', bucket '{bucket}'"
                if start_after:
                    msg += f", starting after {start_after}"
                _S3_LOGGERS[S3Engine.GCS].debug(msg=msg)
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.GCS)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)
    return result


def items_get_tags(prefix: str | Path,
                   max_count: int = None,
                   start_after: str = None,
                   bucket: str = None,
                   client: Client = None,
                   errors: list[str] = None) -> list[dict[str, Any]] | None:
    """
    Recursively retrieve and return custom metadata on a list of items prefixed with *prefix*, in the *GCS* store.

    If *prefix* is not specified, then the bucket's root is used. If *max_count* is a positive integer,
    the number of items returned may be less, but not more, than its value, otherwise it is ignored, and
    all existing items in *prefix* are returned. Optionally, *start_after* identifies the item after which
    the listing must start, thus allowing for paginating the items retrieval operation.

    :param prefix: path prefixing the items to be listed
    :param max_count: the maximum number of items to return (defaults to all items)
    :param start_after: optionally identifies the item after which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: metadata tags on a list of items in *prefix*, or *None* if error or *prefix* not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        # must terminate with '/', otherwise only the folder is considered
        path: str = Path(prefix).as_posix() + "/" if prefix else None
        if not isinstance(max_count, int) or \
           isinstance(max_count, bool) or max_count < 0:
            max_count = 0
        max_keys: int = max_count if 0 < max_count < 1000 else 1000

        # retrieve the tags
        try:
            items: list[dict[str, Any]] = []
            proceed: bool = True
            while proceed:
                # retrieve up to 1000 objects at a time
                reply: HTTPIterator = client.list_blobs(bucket_or_name=bucket,
                                                        max_results=max_keys,
                                                        page_token=start_after,
                                                        prefix=path,
                                                        delimiter="/",
                                                        fields="items(name,metadata),nexPageToken")
                proceed = False
                page = next(reply.pages)
                for gcs_blob in page:
                    item: dict[str, Any] = {"name": gcs_blob.name}
                    if gcs_blob.metadata:
                        item.update(gcs_blob.metadata)
                    items.append(item)

                start_after = reply.next_page_token
                if start_after > 0:
                    max_keys = max_count - len(result) if 0 < max_count - len(result) < 1000 else 1000
                    proceed = True

            # save the items and log the results
            result = items
            if _S3_LOGGERS[S3Engine.GCS]:
                msg: str = f"Listed {len(result)} items in '{prefix}', bucket '{bucket}'"
                if start_after:
                    msg += f", starting after {start_after}"
                _S3_LOGGERS[S3Engine.GCS].debug(msg=msg)
        except Exception as e:
            msg: str = _except_msg(exception=e,
                                   engine=S3Engine.GCS)
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
            if isinstance(errors, list):
                errors.append(msg)
    return result


def items_count(prefix: str | Path | None,
                bucket: str = None,
                client: Client = None,
                errors: list[str] = None) -> int | None:
    """
    Retrieve the number of items prefixed with *prefix*, in the *GCS* store.

    If *prefix* is not specified, then the bucket's root is used. A count operation on the contents
    of a *prefix* may be time-consuming, as the least inefficient way to obtain such information with the
    *boto3* package is by paginating the elements and accounting for the sizes of these pages.

    :param prefix: path prefixing the items to be counted
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the number of items in *prefix*, 0 if *prefix* not found, or *None* if error
    """
    # initialize the return variable
    result: int | None = None

    # retrieve the names of the items to be counted
    curr_errors: list[str] = []
    item_names: list[dict[str, str]] = items_get_info(attributes=["name"],
                                                      prefix=prefix,
                                                      bucket=bucket,
                                                      client=client,
                                                      errors=curr_errors)
    if curr_errors:
        errors.extend(curr_errors)
    else:
        result = len(item_names)

    return result


def items_remove(identifiers: list[str | tuple[str, str]],
                 prefix: str | Path = None,
                 bucket: str = None,
                 client: Client = None,
                 errors: list[str] = None) -> int:
    """
    Remove the items listed in *identifiers* from the *GCS* store.

    The items to be removed are listed in *identifiers*, either with a simple *name*, or with
    a *name,version* pair. If the version is not provided for a given item, then only its
    current (latest) version is removed. Items in *identifiers* are ignored, if not found.

    The removal operation will attempt to continue if errors occur. Thus, make sure to check *errors*,
    besides inspecting the returned value.

    :param identifiers: identifiers for the items to be removed
    :param prefix: optional path prefixing the items to be removed
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional *GCS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        # establish a path prefix
        path: Path = Path(prefix) if isinstance(prefix, str) else prefix

        # GCS allows a maximum of 100 operations per batch request
        pos: int = 0
        size: int = min(100, len(identifiers))
        while size > 0:
            items: list[dict[str, Any]] = []
            for identifier in identifiers[pos:pos+size]:
                if isinstance(identifier, tuple):
                    items.append({
                        "key": (path / identifier[0]).as_posix() if path else identifier[0],
                        "version": int(identifier[1])
                    })
                else:
                    items.append({"key": (path / identifier).as_posix() if path else identifier})
            try:
                gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
                with client.batch():
                    for item in items:
                        gcs_blob: Blob = gcs_bucket.blob(blob_name=item.get("key"),
                                                         generation=item.get("version"))
                        # in the 'batch' context, the delete operation does not happen immediately
                        # (it is queued, to be sent at the end of the 'with' block)
                        gcs_blob.delete()
            except Exception as e:
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
            pos += size
            size = min(1000, len(identifiers) - pos)

    return result


def generate_presigned_url(identifier: str,
                           expires_in: int,
                           prefix: str | Path = None,
                           bucket: str = None,
                           client: Client = None,
                           errors: list[str] = None) -> str:
    """
    Generate a presigned URL that grants time-limited, no credentials required, access to a private GCS object.

    :param identifier: the data identifier
    :param expires_in: time until expiration (in seconds, defaults to 3600)
    :param prefix: optional path prefixing the item to be retrieved
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param client: optional S3 client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the URL generated, or *None* if error or data not found
    """
    # initialize the return variable
    result: str | None = None

    # make sure to have a client
    client = client or get_client(errors=errors)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.GCS,
                                      param=S3Param.BUCKET_NAME)
        # generate the URL
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            gcs_bucket: Bucket = client.bucket(bucket_name=bucket)
            gcs_blob: Blob = gcs_bucket.blob(blob_name=obj_key)
            expiration: timedelta = timedelta(seconds=expires_in)
            result = gcs_blob.generate_signed_url(expiration=expiration,
                                                  method="GET")
            if _S3_LOGGERS[S3Engine.GCS]:
                _S3_LOGGERS[S3Engine.GCS].debug(msg=f"Generated presigned URL for '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            if not isinstance(e, NotFound):
                msg: str = _except_msg(exception=e,
                                       engine=S3Engine.GCS)
                if _S3_LOGGERS[S3Engine.GCS]:
                    _S3_LOGGERS[S3Engine.GCS].error(msg=msg)
                if isinstance(errors, list):
                    errors.append(msg)
    return result
