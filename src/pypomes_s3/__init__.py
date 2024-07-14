from .s3_pomes import (
    s3_access, s3_startup,
    s3_data_store, s3_data_retrieve,
    s3_file_store, s3_file_retrieve,
    s3_object_store, s3_object_retrieve,
    s3_item_exists, s3_item_stat,
    s3_item_remove, s3_items_list, s3_tags_retrieve,
)

__all__ = [
    # s3_pomes
    "s3_access", "s3_startup",
    "s3_data_store", "s3_data_retrieve",
    "s3_file_store", "s3_file_retrieve",
    "s3_object_store", "s3_object_retrieve",
    "s3_item_exists", "s3_item_stat",
    "s3_item_remove", "s3_items_list", "s3_tags_retrieve",
]

from importlib.metadata import version
__version__ = version("pypomes_s3")
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
