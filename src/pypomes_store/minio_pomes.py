from typing import Final, Iterator
from minio import Minio
from minio.datatypes import Object as MinioObject
from minio.commonconfig import Tags
from unidecode import unidecode
import os
import pickle
import tempfile
import uuid
from .env_pomes import APP_PREFIX, env_get_bool, env_get_str

MINIO_BUCKET: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_BUCKET")
MINIO_HOST: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_HOST")
MINIO_ACCESS_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_ACCESS_KEY")
MINIO_SECRET_KEY: Final[str] = env_get_str(f"{APP_PREFIX}_MINIO_SECRET_KEY")
MINIO_SECURE_ACCESS: Final[bool] = env_get_bool(F"{APP_PREFIX}_MINIO_SECURE_ACCESS")
MINIO_TEMP_PATH: Final[str] = env_get_str(F"{APP_PREFIX}_MINIO_TEMP_PATH", tempfile.gettempdir())


def minio_setup(errors: list[str]) -> bool:

    result: bool = True
    try:
        # obtem o cliente MinIO
        minio_client = Minio(endpoint=MINIO_HOST,
                             access_key=MINIO_ACCESS_KEY,
                             secret_key=MINIO_SECRET_KEY,
                             secure=MINIO_SECURE_ACCESS)

        # constrói o bucket, se necessário
        if not minio_client.bucket_exists(bucket_name=MINIO_BUCKET):
            minio_client.make_bucket(bucket_name=MINIO_BUCKET)

    except Exception as e:
        result = False
        errors.append(__minio_except_msg(e))

    return result


# obtem o cliente MinIO
def minio_access(errors: list[str]) -> Minio:

    # inicializa a variável de retorno
    result: Minio | None = None

    # obtem o cliente MinIO
    try:
        result = Minio(endpoint=MINIO_HOST,
                       access_key=MINIO_ACCESS_KEY,
                       secret_key=MINIO_SECRET_KEY,
                       secure=MINIO_SECURE_ACCESS)

    except Exception as e:
        errors.append(__minio_except_msg(e))

    return result


# armazena arquivo no MinIO
def minio_file_store(errors: list[str], basepath: str,
                     identificador: str, filepath: str, mimetype: str, tags: dict = None):

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # foi possível obter o cliente MinIO ?
    if minio_client is not None:
        # sim, armazene o arquivo
        remotepath: str = os.path.join(basepath, identificador)
        # tags foram definidas ?
        if tags is None or len(tags) == 0:
            # não
            doc_tags = None
        else:
            # sim, armazene-as
            doc_tags = Tags(for_object=True)
            for key, value in tags.items():
                # normaliza texto, retirando diacríticos
                doc_tags[key] = unidecode(value)
        try:
            minio_client.fput_object(bucket_name=MINIO_BUCKET,
                                     object_name=remotepath,
                                     file_path=filepath,
                                     content_type=mimetype,
                                     tags=doc_tags)
        except Exception as e:
            errors.append(__minio_except_msg(e))


# recupera o arquivo
def minio_file_retrieve(errors: list[str], basepath: str, identificador: str, filepath: str) -> any:

    # inicializa a variável de retorno
    result: any = None

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # foi possível obter o cliente MinIO ?
    if minio_client is not None:
        # sim, obtenha o arquivo
        remotepath: str = os.path.join(basepath, identificador)
        try:
            result = minio_client.fget_object(bucket_name=MINIO_BUCKET,
                                              object_name=remotepath,
                                              file_path=filepath)
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                errors.append(__minio_except_msg(e))

    return result


# determina se objeto existe no MinIO
def minio_object_exists(errors: list[str], basepath: str, identificador: str = None) -> bool:

    # inicializa a variável de retorno
    result: bool = False

    # o identificador foi informado ?
    if identificador is None:
        # não, objeto é uma pasta
        objs: Iterator = minio_objects_list(errors, basepath)
        for _ in objs:
            result = True
            break
    else:
        # sim, verifique o 'stat' do objeto
        if minio_object_stat(errors, basepath, identificador) is not None:
            result = True

    return result


# retorna o status do objeto - None se objeto não existe
def minio_object_stat(errors: list[str], basepath: str, identificador: str) -> MinioObject:

    # inicializa a variável de retorno
    result: MinioObject | None = None

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # foi possível obter o cliente MinIO ?
    if minio_client is not None:
        # sim, obtenha o status do objeto
        remotepath: str = os.path.join(basepath, identificador)
        try:
            result = minio_client.stat_object(bucket_name=MINIO_BUCKET,
                                              object_name=remotepath)
        except Exception as e:
            if not hasattr(e, "code") or e.code != "NoSuchKey":
                errors.append(__minio_except_msg(e))

    return result


# armazena objeto no MinIO
def minio_object_store(errors: list[str], basepath: str,
                       identificador: str, objeto: any, tags: dict = None):

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # se foi possível obter o cliente MinIO, prossiga
    if minio_client is not None:

        # serializa o objeto em arquivo
        filepath: str = os.path.join(MINIO_TEMP_PATH, str(uuid.uuid4()) + ".pickle")
        with open(filepath, "wb") as f:
            pickle.dump(objeto, f)

        # armazena e remove o arquivo
        minio_file_store(errors, basepath, identificador, filepath, "application/octet-stream", tags)
        os.remove(filepath)


# recupera o objeto
def minio_object_retrieve(errors: list[str], basepath: str, identificador: str) -> any:

    # inicializa a variável de retorno
    result: any = None

    # recupera o arquivo contendo o objeto serializado
    filepath: str = os.path.join(MINIO_TEMP_PATH, str(uuid.uuid4()) + ".pickle")
    stat: any = minio_file_retrieve(errors, basepath, identificador, filepath)

    # o arquivo foi recuperado ?
    if stat is not None:
        # sim, reconstrua o objeto e destrua o arquivo
        with open(filepath, "rb") as f:
            result = pickle.load(f)
        os.remove(filepath)

    return result


def minio_object_delete(errors: list[str], basepath: str, identificador: str = None):

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # foi possível obter o cliente MinIO ?
    if minio_client is not None:
        # sim, o identificador do objeto foi definido ?
        if identificador is None:
            # não, exclua a pasta
            __minio_folder_delete(errors, minio_client, basepath)
        else:
            # sim, exclua o objeto
            remotepath: str = os.path.join(basepath, identificador)
            try:
                minio_client.remove_object(bucket_name=MINIO_BUCKET,
                                           object_name=remotepath)
            except Exception as e:
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    errors.append(__minio_except_msg(e))


# recupera as tags do objeto
def minio_object_tags_retrieve(errors: list[str], basepath: str, identificador: str) -> dict:

    # declara a variável de retorno
    result: dict | None = None

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # foi possível obter o cliente MinIO ?
    if minio_client is not None:
        # sim, prossiga
        remotepath: str = os.path.join(basepath, identificador)
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

    # inicializa a variável de retorno
    result: any = None

    # obtem o cliente MinIO
    minio_client: Minio = minio_access(errors)

    # foi possível obter o cliente MinIO ?
    if minio_client is not None:
        # sim, obtenha a lista de objetos
        try:
            result = minio_client.list_objects(bucket_name=MINIO_BUCKET,
                                               prefix=basepath,
                                               recursive=recursive)
        except Exception as e:
            errors.append(__minio_except_msg(e))

    return result


def __minio_folder_delete(errors: list[str],  minio_client: Minio, basepath: str):

    # percorra a pasta recursivamente, removendo seus objetos
    try:
        objs: Iterator = minio_objects_list(errors, basepath, True)
        for obj in objs:
            try:
                minio_client.remove_object(bucket_name=MINIO_BUCKET,
                                           object_name=obj.object_name)
            except Exception as e:
                # SANITY CHECK: em caso de exclusão concorrente
                if not hasattr(e, "code") or e.code != "NoSuchKey":
                    errors.append(__minio_except_msg(e))
    except Exception as e:
        errors.append(__minio_except_msg(e))


# constrói a mensagem de erro a partir da exceção produzida
def __minio_except_msg(exception: Exception) -> str:

    # interação com o MinIO levantou a exceção "<class 'classe-da-exceção'>"
    cls: str = str(exception.__class__)
    exc_msg: str = f"{cls[7:-1]} - {exception}"
    return f"Error accessing the object storer: {exc_msg}"
