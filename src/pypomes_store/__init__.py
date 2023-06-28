from .azure_pomes import (
    AZURE_CONNECTION_STRING, AZURE_STORAGE_BUCKET,
    blob_exists, blob_retrieve, blob_store, blob_delete, blob_get_mimetype
)
from .minio_pomes import (
    MINIO_BUCKET, MINIO_HOST, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE_ACCESS, MINIO_TEMP_PATH,
    minio_access, minio_file_store, minio_object_store, minio_object_stat,
    minio_object_delete, minio_objects_list, minio_object_retrieve, minio_object_exists,
    minio_object_tags_retrieve, minio_file_retrieve, minio_setup
)

__all__ = [
    # azure_pomes
    AZURE_CONNECTION_STRING, AZURE_STORAGE_BUCKET,
    blob_exists, blob_retrieve, blob_store, blob_delete, blob_get_mimetype,
    # minio_pomes
    MINIO_BUCKET, MINIO_HOST, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE_ACCESS, MINIO_TEMP_PATH,
    minio_access, minio_file_store, minio_object_store, minio_object_stat,
    minio_object_delete, minio_objects_list, minio_object_retrieve, minio_object_exists,
    minio_object_tags_retrieve, minio_file_retrieve, minio_setup
]

__version__ = "0.1.3"
__version_info__ = (0, 1, 3)
