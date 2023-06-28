import io
import sys
# noinspection PyPackageRequirements
from azure.storage.blob import BlobClient, BlobProperties
from typing import Final
from pypomes_core.env_pomes import APP_PREFIX, env_get_str
from pypomes_core.exception_pomes import exc_format

# string de conexão com o Azure
AZURE_CONNECTION_STRING: Final[str] = env_get_str(f"{APP_PREFIX}_AZURE_CONNECTION_STRING")

#  nome do bucket no armazenamento Azure
AZURE_STORAGE_BUCKET: Final[str] = env_get_str(f"{APP_PREFIX}_AZURE_STORAGE_BUCKET")


def blob_exists(errors: list[str], blob_path: str,
                bucket_name: str = AZURE_STORAGE_BUCKET) -> bool:
    """
    Verifica a existência do arquivo apontado por *blob_path*, dentro de *bucket_name*.

    :param errors: eventuais erros ocorridos na invocação da função
    :param blob_path: caminho do arquivo no bucket
    :param bucket_name: o nome do bucket (AZURE_STORAGE_BUCKET, se não especificado)
    :return: True se o arquivo existe, False em caso contrário, ou None se houve erro
    """
    # inicializa variável de retorno
    result: bool | None = None

    try:
        with BlobClient.from_connection_string(
            conn_str=AZURE_CONNECTION_STRING,
            container_name=bucket_name,
            blob_name=blob_path
        ) as client:
            result = client.exists()
    except Exception as e:
        errors.append(__azure_except_msg(e))

    return result


def blob_retrieve(errors: list[str], blob_path: str,
                  bucket_name: str = AZURE_STORAGE_BUCKET) -> bytes:
    """
    Obtem e retorna o conteúdo *raw* do arquivo apontado por *blob_path*, dentro de *bucket_name*.

    :param errors: eventuais erros ocorridos na invocação da função
    :param blob_path: caminho do arquivo no bucket
    :param bucket_name: o nome do bucket (AZURE_STORAGE_BUCKET, se não especificado)
    :return: o conteúdo do blob, ou None se houve erro
    """
    # inicializa variável de retorno
    result: bytes | None = None

    try:
        with BlobClient.from_connection_string(
            conn_str=AZURE_CONNECTION_STRING,
            container_name=bucket_name,
            blob_name=blob_path
        ) as client:
            stream: io.BytesIO = io.BytesIO()
            client.download_blob().readinto(stream)
            stream.seek(0)
            result = stream.read()
    except Exception as e:
        errors.append(__azure_except_msg(e))

    return result


def blob_store(errors: list[str], content: bytes, blob_path: str,
               bucket_name: str = AZURE_STORAGE_BUCKET) -> bool:
    """
    Armazena o conteúdo *content* no caminho apontado por *blob_path*, dentro de *bucket_name*.

    :param errors: eventuais erros ocorridos na invocação da função
    :param content: conteúdo a ser armazenado
    :param blob_path: caminho do arquivo no bucket
    :param bucket_name: o nome do bucket (AZURE_STORAGE_BUCKET, se não especificado)
    :return: True se a operação foi bem sucedida, ou False em caso contrário
    """
    # declara a variável de retorno
    result: bool

    try:
        with BlobClient.from_connection_string(
            conn_str=AZURE_CONNECTION_STRING,
            container_name=bucket_name,
            blob_name=blob_path
        ) as client:
            stream: io.BytesIO = io.BytesIO(content)
            stream.seek(0)
            client.upload_blob(data=stream,
                               blob_type="BlockBlob",
                               length=len(content),
                               overwrite=True)
            result = True
    except Exception as e:
        result = False
        errors.append(__azure_except_msg(e))

    return result


def blob_delete(errors: list[str], blob_path: str,
                bucket_name: str = AZURE_STORAGE_BUCKET) -> bool:
    """
    Remove o arquivo apontado por *blob_path*, dentro de *bucket_name*, e todos os seus *snapshots*.

    :param errors: eventuais erros ocorridos na invocação da função
    :param blob_path: caminho do arquivo no bucket
    :param bucket_name: o nome do bucket (AZURE_STORAGE_BUCKET, se não especificado)
    :return: True se a operação foi bem sucedida, ou False em caso contrário
    """
    # declara variável de retorno
    result: bool

    try:
        with BlobClient.from_connection_string(
            conn_str=AZURE_CONNECTION_STRING,
            container_name=bucket_name,
            blob_name=blob_path
        ) as client:
            client.delete_blob(delete_snapshots="include")
            result = True
    except Exception as e:
        result = False
        errors.append(__azure_except_msg(e))

    return result


def blob_get_mimetype(errors: list[str], blob_path: str,
                      bucket_name: str = AZURE_STORAGE_BUCKET) -> str:
    """
    Obtem e retorna o texxto contido no documento apontado por *file_path*, dentro de  *bucket_name*.
    Esse documento deve ser do tipo HTML ou PDF.

    :param errors: eventuais erros ocorridos na invocação da função
    :param blob_path: caminho do arquivo no bucket
    :param bucket_name: o nome do bucket (AZURE_STORAGE_BUCKET, se não especificado)
    :return: o texto do blob, codificado em UTF-8
    """

    # inicializa a variável de retorno
    result: str | None = None

    try:
        with BlobClient.from_connection_string(
            conn_str=AZURE_CONNECTION_STRING,
            container_name=bucket_name,
            blob_name=blob_path
        ) as client:
            props: BlobProperties = client.get_blob_properties()
            result = props.get("content_settings").get("content_type")
    except Exception as e:
        errors.append(__azure_except_msg(e))

    return result


def __azure_except_msg(exception: Exception) -> str:
    """
    Formata e retorna a mensagem de erro correspondente à exceção levantada no acesso ao Azure.

    :param exception: A exceção levantada
    :return: A mensagem de erro formatada
    """
    # TODO
    return exc_format(exception, sys.exc_info())


# testes do acesso ao Azure
# if __name__ == "__main__":
#
#     # print errors
#     def __print_errors(errors: list[str], op):
#         if len(errors) > 0:
#             print(f"\nErrors in '{op}':")
#             for error in errors:
#                 print(error)
#
#     errors: list[str] = []
#     content: bytes = b"This is the content of a sample text file."
#     file_path: str = "/temp/sample.txt"
#
#     # testa a verificação de existência do arquivo
#     exists: bool = blob_exists(errors, file_path)
#     __print_errors(errors, "blob_exists")
#     assert exists is not None, "Failed verifying file"
#
#     # testa armazenamento de arquivo
#     if not exists:
#         success = blob_store(errors, content, file_path)
#         __print_errors(errors, "blob_store")
#         assert success, "Failed storing file"
#
#     # testa recuperação do tipo do arquivo
#     mimetype: str = blob_get_mimetype(errors, file_path)
#     __print_errors(errors, "blob_get_mimetype")
#     assert mimetype is not None, "Failed retrieving file mimetype"
#
#     # testa recuperação do conteúdo do arquivo
#     retrieved: bytes = blob_retrieve(errors, file_path)
#     __print_errors(errors, "blob_retrieve")
#     assert retrieved is not None, "Failed retrieving file content"
#     print(f"Conteudo recuperado: {content}")
#
#     # testa a exclusão do arquivo
#     success = blob_delete(errors, file_path)
#     __print_errors(errors, "blob_delete")
#     assert success, "Failed Deleting file"
