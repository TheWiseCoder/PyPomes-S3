from .s3_common import (
    S3Engine, S3Param
)
from .s3_pomes import (
    s3_setup, s3_set_logger,
    s3_get_engines, s3_get_param, s3_get_params,
    s3_startup, s3_get_client,
    s3_data_store, s3_data_retrieve,
    s3_file_store, s3_file_retrieve,
    s3_object_store, s3_object_retrieve,
    s3_item_exists, s3_item_get_info,
    s3_item_get_tags, s3_item_remove, s3_items_remove,
    s3_prefix_count, s3_prefix_list, s3_prefix_remove
)

__all__ = [
    # s3_common
    "S3Engine", "S3Param",
    # s3_pomes
    "s3_setup", "s3_set_logger",
    "s3_get_engines", "s3_get_param", "s3_get_params",
    "s3_startup", "s3_get_client",
    "s3_data_store", "s3_data_retrieve",
    "s3_file_store", "s3_file_retrieve",
    "s3_object_store", "s3_object_retrieve",
    "s3_item_exists", "s3_item_get_info",
    "s3_item_get_tags", "s3_item_remove", "s3_items_remove",
    "s3_prefix_count", "s3_prefix_list", "s3_prefix_remove"
]

from importlib.metadata import version
__version__ = version("pypomes_s3")
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
