from .s3_pomes import (
    s3_access, s3_startup, s3_file_store, s3_object_store, s3_object_stat,
    s3_object_delete, s3_objects_list, s3_object_retrieve, s3_object_exists,
    s3_object_tags_retrieve, s3_file_retrieve,
)

__all__ = [
    # s3_pomes
    "s3_access", "s3_startup", "s3_file_store", "s3_object_store", "s3_object_stat",
    "s3_object_delete", "s3_objects_list", "s3_object_retrieve", "s3_object_exists",
    "s3_object_tags_retrieve", "s3_file_retrieve",
]

from importlib.metadata import version
__version__ = version("pypomes_s3")
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
