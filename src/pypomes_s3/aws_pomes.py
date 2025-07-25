import boto3
from botocore.client import BaseClient, Paginator
from botocore.paginate import PageIterator
from io import BytesIO
from logging import Logger
from pathlib import Path
from pypomes_core import Mimetype
from typing import Any, BinaryIO

from .s3_common import (
    S3Engine, S3Param, _get_param, _get_params, _normalize_tags, _except_msg
)


def get_client(errors: list[str] | None,
               logger: Logger = None) -> BaseClient | None:
    """
    Obtain and return a *AWS* client object.

    :param errors: incidental error messages
    :param logger: optional logger
    :return: the AWS client object, or *None* if error
    """
    # initialize the return variable
    result: BaseClient | None = None

    # retrieve the access parameters
    aws_params: dict[S3Param, Any] = _get_params(engine=S3Engine.AWS)

    # obtain the AWS client
    try:
        result = boto3.client(service_name="s3",
                              region_name=aws_params.get(S3Param.REGION_NAME),
                              use_ssl=aws_params.get(S3Param.SECURE_ACCESS),
                              verify=False,
                              endpoint_url=aws_params.get(S3Param.ENDPOINT_URL),
                              aws_access_key_id=aws_params.get(S3Param.ACCESS_KEY),
                              aws_secret_access_key=aws_params.get(S3Param.SECRET_KEY))
        if logger:
            logger.debug(msg="AWS client created")

    except Exception as e:
        if isinstance(errors, list):
            errors.append(_except_msg(exception=e,
                                      engine=S3Engine.AWS))
    return result


def startup(errors: list[str] | None,
            bucket: str,
            logger: Logger = None) -> bool:
    """
    Prepare the *AWS* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the S3 service is fully functional.

    :param errors: incidental error messages
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param logger: optional logger
    :return: *True* if service is fully functional, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # obtain a client
    client: BaseClient = get_client(errors=errors,
                                    logger=logger)
    # was the client obtained ?
    if client:
        # yes, proceed
        try:
            client.head_bucket(Bucket=bucket)
            result = True
            if logger:
                logger.debug(msg=f"Started AWS, bucket '{bucket}' asserted")
        except Exception as e1:
            # log the exception and try to create a bucket
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e1,
                                          engine=S3Engine.AWS))
            try:
                client.create_bucket(Bucket=bucket)
                result = True
                if logger:
                    logger.debug(msg=f"Started AWS, bucket '{bucket}' created")
            except Exception as e2:
                if isinstance(errors, list):
                    errors.append(_except_msg(exception=e2,
                                              engine=S3Engine.AWS))
    return result


def data_retrieve(errors: list[str] | None,
                  identifier: str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  data_range: tuple[int, int] = None,
                  client: BaseClient = None,
                  logger: Logger = None) -> bytes | None:
    """
    Retrieve data from the *AWS* store.

    :param errors: incidental error messages
    :param identifier: the data identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to retrieve the data from
    :param data_range: the begin-end positions within the data (in bytes, defaults to *None* - all bytes)
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the bytes retrieved, or *None* if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    # was the client obtained ?
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        # retrieve the data
        obj_range: str = f"bytes={data_range[0]}-{data_range[1]}" if data_range else None
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            reply: dict[str: Any] = client.get_object(Bucket=bucket,
                                                      Key=obj_key,
                                                      Range=obj_range)
            result = reply["Body"]
            if logger:
                logger.debug(msg=f"Retrieved '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if isinstance(errors, list) and \
               (not hasattr(e, "code") or e.code != "NoSuchKey"):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def data_store(errors: list[str] | None,
               identifier: str,
               data: bytes | str | BinaryIO,
               bucket: str = None,
               prefix: str | Path = None,
               length: int = None,
               mimetype: Mimetype | str = Mimetype.BINARY,
               tags: dict[str, str] = None,
               client: BaseClient = None,
               logger: Logger = None) -> dict[str, str] | None:
    """
    Store *data* at the *AWS* store.

    In case *length* cannot be determined, it should be set to *None*.

    On success, this operation returns a *dict* with information related to the stored item.
    Unfortunately, it is not possible to detail the information returned, as there is no consistency
    in the responses. In fact, the responses vary wildly with the different *AWS* implementations.
    It should also be noted that those responses are not guaranteed to be serializable.

    :param errors: incidental error messages
    :param identifier: the data identifier
    :param data: the data to store
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param length:  the length of the data
    :param prefix: optional path specifying the location to store the file at
    :param mimetype: the data mimetype
    :param tags: optional metadata tags describing the file
    :param client: optional AWS client (obtains a new one, if not provided)
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
        bucket = bucket or _get_param(engine=S3Engine.AWS,
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

            # most implementations do not comply with the expected, and well-documented, response
            result = client.put_object(Body=bin_data,
                                       Bucket=bucket,
                                       ContentLength=length,
                                       ContentType=mimetype,
                                       Key=obj_key,
                                       Metadata=_normalize_tags(tags))
            if logger:
                logger.debug(msg=(f"Stored '{obj_key}', bucket '{bucket}', "
                                  f"content type '{mimetype}', tags '{tags}'"))
        except Exception as e:
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def file_retrieve(errors: list[str] | None,
                  identifier: str,
                  filepath: Path | str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  client: BaseClient = None,
                  logger: Logger = None) -> bool | None:
    """
    Retrieve a file from the *AWS* store.

    :param errors: incidental error messages
    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to retrieve the file from
    :param client: optional AWS client (obtains a new one, if not provided)
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
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            file_path: str = Path(filepath).as_posix()
            client.download_file(Bucket=bucket,
                                 Filename=file_path,
                                 Key=obj_key)
            result = Path(filepath).exists()
            if logger:
                logger.debug(msg=f"{obj_key}', bucket '{bucket}', "
                                 f"{'retrieved' if result else 'not retrieved'}")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if isinstance(errors, list) and \
               (not hasattr(e, "code") or e.code != "NoSuchKey"):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def file_store(errors: list[str] | None,
               identifier: str,
               filepath: Path | str,
               mimetype: Mimetype | str,
               bucket: str = None,
               prefix: str | Path = None,
               tags: dict[str, str] = None,
               client: BaseClient = None,
               logger: Logger = None) -> bool:
    """
    Store a file at the *AWS* store.

    :param errors: incidental error messages
    :param identifier: the file identifier, tipically a file name
    :param filepath: optional path specifying where the file is
    :param mimetype: the file mimetype
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to store the file at
    :param tags: optional metadata tags describing the file
    :param client: optional AWS client (obtains a new one, if not provided)
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
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)

        extra_args: dict[str, Any] | None = None
        if mimetype or tags:
            extra_args = {}
            if mimetype:
                if isinstance(mimetype, Mimetype):
                    mimetype = mimetype.value
                extra_args["ContentType"] = mimetype
            if tags:
                extra_args["Metadata"] = _normalize_tags(tags)

        # store the file
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            file_path: str = Path(filepath).as_posix()
            # returns 'None'
            client.upload_file(Filename=file_path,
                               Bucket=bucket,
                               Key=obj_key,
                               ExtraArgs=extra_args)
            if logger:
                logger.debug(msg=(f"Stored '{obj_key}', bucket '{bucket}', "
                                  f"from '{file_path}', content type '{mimetype}', tags '{tags}'"))
            result = True
        except Exception as e:
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def item_get_info(errors: list[str] | None,
                  identifier: str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  client: BaseClient = None,
                  logger: Logger = None) -> dict[str, Any] | None:
    """
    Retrieve information about an item in the *AWS* store.

    The item might be interpreted as unspecified data, a file, or an object.
    The information returned is shown below. Please refer to the published *AWS*
    documentation for the meaning of any of these attributes.
    {
        'DeleteMarker': True|False,
        'LastModified': datetime(2015, 1, 1),
        'VersionId': 'string',
        'RequestCharged': 'requester',
        'ETag': 'string',
        'Checksum': {
            'ChecksumCRC32': 'string',
            'ChecksumCRC32C': 'string',
            'ChecksumSHA1': 'string',
            'ChecksumSHA256': 'string'
        },
        'ObjectParts': {
            'TotalPartsCount': 123,
            'PartNumberMarker': 123,
            'NextPartNumberMarker': 123,
            'MaxParts': 123,
            'IsTruncated': True|False,
            'Parts': [
                {
                    'PartNumber': 123,
                    'Size': 123,
                    'ChecksumCRC32': 'string',
                    'ChecksumCRC32C': 'string',
                    'ChecksumSHA1': 'string',
                    'ChecksumSHA256': 'string'
                },
            ]
        },
        'StorageClass': 'STANDARD' | 'REDUCED_REDUNDANCY' | 'STANDARD_IA' | 'ONEZONE_IA' |
                        'INTELLIGENT_TIERING' | 'GLACIER' | 'DEEP_ARCHIVE' | 'OUTPOSTS' |
                        'GLACIER_IR' | 'SNOW' | 'EXPRESS_ONEZONE',
        'ObjectSize': 123
    }

    :param errors: incidental error messages
    :param identifier: the item identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying where to locate the item
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information about the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            result = client.get_object_attributes(Bucket=bucket,
                                                  Key=obj_key)
            if logger:
                logger.debug(msg=f"Got info for '{obj_key}', bucket '{bucket}'")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if isinstance(errors, list) and \
               (not hasattr(e, "code") or e.code != "NoSuchKey"):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def item_get_tags(errors: list[str] | None,
                  identifier: str,
                  bucket: str = None,
                  prefix: str | Path = None,
                  client: BaseClient = None,
                  logger: Logger = None) -> dict[str, str] | None:
    """
    Retrieve the existing metadata tags for an item in the *AWS* store.

    The item might be interpreted as unspecified data, a file, or an object.
    If item has no associated metadata tags, an empty *dict* is returned.
    The information returned by the native invocation is shown below. The *dict* returned is the
    value of the *Metadata* attribute. Please refer to the published *AWS* documentation
    for the meaning of any of these attributes.
    {
        'DeleteMarker': True|False,
        'AcceptRanges': 'string',
        'Expiration': 'string',
        'Restore': 'string',
        'ArchiveStatus': 'ARCHIVE_ACCESS'|'DEEP_ARCHIVE_ACCESS',
        'LastModified': datetime(2015, 1, 1),
        'ContentLength': 123,
        'ChecksumCRC32': 'string',
        'ChecksumCRC32C': 'string',
        'ChecksumSHA1': 'string',
        'ChecksumSHA256': 'string',
        'ETag': 'string',
        'MissingMeta': 123,
        'VersionId': 'string',
        'CacheControl': 'string',
        'ContentDisposition': 'string',
        'ContentEncoding': 'string',
        'ContentLanguage': 'string',
        'ContentType': 'string',
        'Expires': datetime(2015, 1, 1),
        'WebsiteRedirectLocation': 'string',
        'ServerSideEncryption': 'AES256'|'aws:kms'|'aws:kms:dsse',
        'Metadata': {
            'string': 'string'
        },
        'SSECustomerAlgorithm': 'string',
        'SSECustomerKeyMD5': 'string',
        'SSEKMSKeyId': 'string',
        'BucketKeyEnabled': True|False,
        'StorageClass': 'STANDARD' | 'REDUCED_REDUNDANCY' | 'STANDARD_IA' | 'ONEZONE_IA' |
                        'INTELLIGENT_TIERING' | 'GLACIER' | 'DEEP_ARCHIVE' | 'OUTPOSTS' |
                        'GLACIER_IR' | 'SNOW' | 'EXPRESS_ONEZONE',
        'RequestCharged': 'requester',
        'ReplicationStatus': 'COMPLETE'|'PENDING'|'FAILED'|'REPLICA'|'COMPLETED',
        'PartsCount': 123,
        'ObjectLockMode': 'GOVERNANCE'|'COMPLIANCE',
        'ObjectLockRetainUntilDate': datetime(2015, 1, 1),
        'ObjectLockLegalHoldStatus': 'ON'|'OFF'
    }

    :param errors: incidental error messages
    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to retrieve the item from
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: the metadata tags associated with the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        try:
            if prefix:
                obj_path: Path = Path(prefix) / identifier
                obj_key: str = obj_path.as_posix()
            else:
                obj_key: str = identifier
            head_info: dict[str, str] = client.head_object(Bucket=bucket,
                                                           Key=obj_key)
            result = head_info.get("Metadata")
            if logger:
                logger.debug(msg=f"Retrieved '{obj_key}', bucket '{bucket}', tags '{result}'")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if isinstance(errors, list) and \
               (not hasattr(e, "code") or e.code != "NoSuchKey"):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))

    return result


def item_remove(errors: list[str] | None,
                identifier: str,
                version: str = None,
                bucket: str = None,
                prefix: str | Path = None,
                client: BaseClient = None,
                logger: Logger = None) -> bool | None:
    """
    Remove an item from the *AWS* store.

    If *version* is not specified, then only the item's current (latest) version is removed.
    To remove items in a given folder, use *s3_items_remove()*, instead.

    :param errors: incidental error messages
    :param identifier: the item identifier
    :param version: optional version of the item to be removed (defaults to its current version)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to delete the item at
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: *True* if the item was successfully removed, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # make sure to have a client
    client = client or get_client(errors=errors, logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        if prefix:
            path: Path = Path(prefix) / identifier
            key: str = path.as_posix()
        else:
            key: str = identifier
        # remove the item
        try:
            # expected response:
            # {
            #     'DeleteMarker': True|False,
            #     'VersionId': 'string',
            #     'RequestCharged': 'requester'
            # }
            reply: dict[str, Any] = client.delete_object(Bucket=bucket,
                                                         Key=key,
                                                         VersionId=version)
            if logger:
                logger.debug(msg=f"Deleted '{key}', bucket '{bucket}'")
            result = reply.get("DeleteMarker")
        except Exception as e:
            # noinspection PyUnresolvedReferences
            if isinstance(errors, list) and \
               (not hasattr(e, "code") or e.code != "NoSuchKey"):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def items_count(errors: list[str] | None,
                bucket: str = None,
                prefix: str | Path = None,
                client: BaseClient = None,
                logger: Logger = None) -> int | None:
    """
    Retrieve the number of items in *prefix*, in the *AWS* store.

    A count operation on the contents of a *prefix* may be time-consuming, as the least inefficient way to
    obtain such information with the *boto3* package is by paginating the elements and accounting for the
    sizes of these pages.

    :param errors: incidental error messages
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to retrieve the items from
    :param client: optional AWS client (obtains a new one, if not provided)
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
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        try:
            # initialize a page iterator
            paginator: Paginator = client.get_paginator(operation_name="list_objects_v2")
            iterator: PageIterator = paginator.paginate(Bucket=bucket,
                                                        Prefix=Path(prefix).as_posix() if prefix else None,
                                                        Delimiter="/")
            # traverse the pages, counting the items
            result = sum(page.get("KeyCount", 0) for page in iterator)
            if logger:
                logger.debug(msg=f"Counted {result} items in '{prefix}', bucket '{bucket}'")
        except Exception as e:
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def items_list(errors: list[str] | None,
               max_count: int = None,
               start_after: str = None,
               bucket: str = None,
               prefix: str | Path = None,
               client: BaseClient = None,
               logger: Logger = None) -> list[dict[str, Any]] | None:
    """
    Recursively retrieve and return information on a list of items in *prefix*, in the *AWS* store.

    If *max_count* is a positive integer, the number of items returned may be less, but not more,
    than its value, otherwise it is ignored and all existing items in *prefix* are returned.
    Optionally, *start_after* identifies the item after which the listing must start, thus allowing
    for paginating the items retrieval operation.

    The information returned by the native invocation is shown below. The *list* returned contains the items
    of the *Contents* attribute, lexicographically sorted by its *Key* attribute.
    Refer to the published *AWS* documentation for the meaning of these attributes.
    {
        'IsTruncated': True|False,
        'Contents': [
            {
                'Key': 'string',
                'LastModified': datetime(2015, 1, 1),
                'ETag': 'string',
                'ChecksumAlgorithm': [
                    'CRC32'|'CRC32C'|'SHA1'|'SHA256',
                ],
                'Size': 123,
                'StorageClass': 'STANDARD' | 'REDUCED_REDUNDANCY' | 'STANDARD_IA' | 'ONEZONE_IA' |
                                'INTELLIGENT_TIERING' | 'GLACIER' | 'DEEP_ARCHIVE' | 'OUTPOSTS' |
                                'GLACIER_IR' | 'SNOW' | 'EXPRESS_ONEZONE',
                'Owner': {
                    'DisplayName': 'string',
                    'ID': 'string'
                },
                'RestoreStatus': {
                    'IsRestoreInProgress': True|False,
                    'RestoreExpiryDate': datetime(2015, 1, 1)
                }
            },
        ],
        'Name': 'string',
        'Prefix': 'string',
        'Delimiter': 'string',
        'MaxKeys': 123,
        'CommonPrefixes': [
            {
                'Prefix': 'string'
            },
        ],
        'EncodingType': 'url',
        'KeyCount': 123,
        'ContinuationToken': 'string',
        'NextContinuationToken': 'string',
        'StartAfter': 'string',
        'RequestCharged': 'requester'
    }

    :param errors: incidental error messages
    :param max_count: the maximum number of items to return (defaults to all items)
    :param start_after: optionally identifies the item at which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to retrieve the items from
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: information on a list of items in *prefix*, or *None* if error or *prefix* not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # make sure to have a client
    client = client or get_client(errors=errors,
                                  logger=logger)
    if client:
        # make sure to have a bucket
        bucket = bucket or _get_param(engine=S3Engine.AWS,
                                      param=S3Param.BUCKET_NAME)
        # must terminate with '/', otherwise only the folder is considered
        path: str = Path(prefix).as_posix() + "/" if prefix else None
        if not isinstance(max_count, int) or \
           isinstance(max_count, bool) or max_count < 0:
            max_count = 0
        max_keys: int = max_count if 0 < max_count < 1000 else 1000
        try:
            items: list[dict[str, Any]] = []
            proceed: bool = True
            while proceed:
                # retrieve up to 1000 objects at a time
                reply: dict[str, Any]
                # will raise an error if 'start_after' is 'None'
                if start_after:
                    reply = client.list_objects_v2(Bucket=bucket,
                                                   Prefix=path,
                                                   Delimiter="/",
                                                   MaxKeys=max_keys,
                                                   StartAfter=start_after)
                else:
                    reply = client.list_objects_v2(Bucket=bucket,
                                                   Prefix=path,
                                                   Delimiter="/",
                                                   MaxKeys=max_keys)
                # retrieve from the list (it might be empty)
                proceed = False
                objs: list[dict[str, Any]] = reply.get("Contents")
                if objs:
                    rem: int = min(max_count - len(items), len(objs)) if max_count else len(objs)
                    items.extend(objs[:rem])
                    rem = max_count - len(items) if max_count else 1000
                    if rem > 0:
                        # get the last key read
                        start_after = objs[-1].get("Key")
                        # set the value for the 'MaxKeys' parameter in the next objects retrieval
                        max_keys = min(max_keys, rem)
                        proceed = True

            # save the items and log the results
            result = items
            if logger:
                msg: str = f"Listed {len(result)} items in '{prefix}', bucket '{bucket}'"
                if start_after:
                    msg += f", starting after {start_after}"
                logger.debug(msg=msg)
        except Exception as e:
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e,
                                          engine=S3Engine.AWS))
    return result


def items_remove(errors: list[str] | None,
                 identifiers: list[str | tuple[str, str]] = None,
                 bucket: str = None,
                 prefix: str | Path = None,
                 client: BaseClient = None,
                 logger: Logger = None) -> int:
    """
    Remove the items, listed in *identifiers* and contained in *prefix*, from the *AWS* store.

    The items to be removed are listed in *identifiers*, either with a simple *name*, or with
    a *name,version* pair. If the version is not provided for a given item, then only its
    current (latest) version is removed. Either *identifiers* or *prefix*, or both, must be provided.
    If *identifiers* is not specified, then all the current versions of the items in *prefix* are removed.
    Items in *identifiers* are ignored, if not found.

    The removal operation will attempt to continue if errors occur. Thus, make sure to check *errors*,
    besides inspecting the returned value.

    :param errors: incidental error messages
    :param identifiers: identifiers for the items to be removed (defaults to all items in *prefix*)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path specifying the location to remove the items from
    :param client: optional AWS client (obtains a new one, if not provided)
    :param logger: optional logger
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    if not identifiers and not prefix:
        err_msg: str = "Either 'identifiers' or 'prefix', or both, must be provided"
        if logger:
            logger.error(msg=err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)
    else:
        # make sure to have a client
        client = client or get_client(errors=errors,
                                      logger=logger)
        if client:
            # make sure to have a bucket
            bucket = bucket or _get_param(engine=S3Engine.AWS,
                                          param=S3Param.BUCKET_NAME)
            if not identifiers:
                items: list[dict[str, Any]] = items_list(errors=errors,
                                                         bucket=bucket,
                                                         prefix=prefix,
                                                         client=client,
                                                         logger=logger)
                identifiers = [i.get("Key") for i in (items or [])]
            if not errors:
                # a maximum of 1000 items may be sent for deletion
                pos: int = 0
                size: int = min(1000, len(identifiers))
                while size > 0:
                    items: list[dict[str, Any]] = []
                    for identifier in identifiers[pos:pos+size]:
                        if isinstance(identifier, tuple):
                            items.append({
                                "Key": identifier[0],
                                "VersionId": identifier[1]
                            })
                        else:
                            items.append({"Key": identifier})
                    delete: dict[str, Any] = {
                        "Objects": items
                    }
                    try:
                        reply: dict[str, Any] = client.delete_objects(Bucket=bucket,
                                                                      Delete=delete)
                        result += len(reply.get("Deleted") or [])
                        # acknowledge errors eventually reported
                        errors.extend([f"Error {e.get('Code')} ({e.get('Message')}) "
                                       f"removing document ({e.get('Key')}, v. {e.get('VersionId')}"
                                       for e in (reply.get("Errors") or [])])
                    except Exception as e:
                        errors.append(_except_msg(exception=e,
                                                  engine=S3Engine.AWS))
                    pos += size
                    size = min(1000, len(identifiers) - pos)
    return result
