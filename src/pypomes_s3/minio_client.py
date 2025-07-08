from minio import Minio
from minio.credentials.providers import Provider
from types import TracebackType
from urllib3 import PoolManager


class MinioCM:
    """
    Simple Storage Service (*S3*) client, extended to provide context-managed operations.

    Please, refer to the *MinIO* package documentation for details on its implementation.
    """
    def __init__(self,
                 endpoint: str,
                 access_key: str | None = None,
                 secret_key: str | None = None,
                 session_token: str | None = None,
                 secure: bool = True,
                 region: str | None = None,
                 http_client: PoolManager | None = None,
                 credentials: Provider | None = None,
                 cert_check: bool = True) -> None:
        """
        Extend *MinIO* package's implementation of a Simple Storage Service (*S3*) client, .

        The aim is to provide context-managed *MinIO* clients.
        Please, refer to the *MinIO* package documentation for details on its implementation.

        :param endpoint: Hostname of a S3 service
        :param access_key: Access key (aka user ID) of your account in S3 service
        :param secret_key: Secret Key (aka password) of your account in S3 service
        :param session_token: Session token of your account in S3 service
        :param secure: Flag to indicate to use secure (TLS) connection to S3 service or not
        :param region: Region name of buckets in S3 service
        :param http_client: Customized HTTP client
        :param credentials: Credentials provider of your account in S3 service
        :param cert_check: Flag to indicate to verify SSL certificate or not
        """
        self.minio_client: Minio = Minio(endpoint=endpoint,
                                         access_key=access_key,
                                         secret_key=secret_key,
                                         session_token=session_token,
                                         secure=secure,
                                         region=region,
                                         http_client=http_client,
                                         credentials=credentials,
                                         cert_check=cert_check)

    def __enter__(self) -> Minio:
        """
        First step in providing a context-managed *MinIO* client.

        :return: a Minio client object
        """
        return self.minio_client

    def __exit__(self,
                 exception_type: type[BaseException] | None,
                 exception_value: BaseException | None,
                 traceback: TracebackType | None) -> bool:
        """
        Last step in providing a context-managed *MinIO* client.
        """
        self.minio_client = None

        # make sure an eventual exception is propagated
        return exception_type is None
