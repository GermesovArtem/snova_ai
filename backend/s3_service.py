import os
import uuid
import logging
import aioboto3
from dotenv import load_dotenv
from botocore.config import Config

load_dotenv()

logger = logging.getLogger(__name__)

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

async def upload_file_to_s3(file_bytes: bytes, ext: str) -> str:
    """
    Асинхронно загружает файл (байты) в S3 бакет и возвращает публичный URL.
    :param file_bytes: Содержимое файла в байтах.
    :param ext: Расширение файла (например, '.jpg', '.png'). Возвращается ссылка для доступа.
    """
    if not all([S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME]):
        logger.error("S3 configuration is missing in environment variables.")
        raise ValueError("S3 config incomplete")

    filename = f"{uuid.uuid4()}{ext}"
    logger.info(f"Uploading {filename} to S3 bucket {S3_BUCKET_NAME}")

    session = aioboto3.Session()
    
    # Убираем '/ru-3' из endpoint_url и указываем регион явно, если необходимо.
    # Настройка для использования Path-Style (https://hostname/bucket/key)
    config = Config(s3={'addressing_style': 'path'})

    try:
        async with session.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=config
        ) as s3_client:
            
            # Определяем Content-Type
            content_type = 'image/jpeg'
            if ext.lower() in ['.png']:
                content_type = 'image/png'
            elif ext.lower() in ['.webp']:
                content_type = 'image/webp'
            
            logger.info(f"Uploading {filename} to S3 bucket {S3_BUCKET_NAME} with Content-Type: {content_type}")
            
            await s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=filename,
                Body=file_bytes,
                ContentType=content_type,
                ACL='public-read' # Делаем файл публичным по умолчанию
            )
            
            # Используем ПУТЬ (path-style): https://endpoint/bucket/file
            # Это более надежно для публичного доступа в Selectel
            clean_endpoint = S3_ENDPOINT_URL.rstrip('/')
            if 'storage.selcloud.ru' in clean_endpoint and not clean_endpoint.startswith('https://'):
                 clean_endpoint = f"https://{clean_endpoint}"
                 
            public_url = f"{clean_endpoint}/{S3_BUCKET_NAME}/{filename}"
            logger.info(f"Successfully uploaded to S3. Public URL: {public_url}")
            
            return public_url
            
    except Exception as e:
        logger.error(f"S3 Upload Failed! Endpoint: {S3_ENDPOINT_URL}, Bucket: {S3_BUCKET_NAME}, Error: {e}", exc_info=True)
        raise e

async def get_presigned_url(filename: str, expires_in: int = 3600) -> str:
    """
    Генерирует временную (pre-signed) ссылку для доступа к приватному объекту в S3.
    Это надежнее публичных ссылок для KIE AI.
    """
    if not all([S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME]):
        raise ValueError("S3 config incomplete")

    session = aioboto3.Session()
    config = Config(s3={'addressing_style': 'path'})
    async with session.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=config
    ) as s3_client:
        url = await s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': filename},
            ExpiresIn=expires_in
        )
        return url
