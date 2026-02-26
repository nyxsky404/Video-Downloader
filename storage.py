import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    def save_file(self, local_path: Path, remote_name: str) -> str:
        pass

    @abstractmethod
    def get_file_url(self, filename: str) -> str:
        pass

    @abstractmethod
    def file_exists(self, filename: str) -> bool:
        pass

    @abstractmethod
    def get_download_dir(self) -> Path:
        pass


class LocalStorage(StorageBackend):
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized: {self.download_dir}")

    def save_file(self, local_path: Path, remote_name: str) -> str:
        return f"/downloads/{remote_name}"

    def get_file_url(self, filename: str) -> str:
        return f"/downloads/{filename}"

    def file_exists(self, filename: str) -> bool:
        return (self.download_dir / filename).exists()

    def get_download_dir(self) -> Path:
        return self.download_dir


class S3Storage(StorageBackend):
    def __init__(self, bucket_name: str, region: str = "ap-south-1"):
        self.bucket_name = bucket_name
        self.region = region
        self._local_temp_dir = Path("/tmp/downloads")
        self._local_temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import NoCredentialsError, ClientError, BotoCoreError
            
            config = Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'},
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
            self.s3_client = boto3.client(
                's3',
                region_name=region,
                endpoint_url=f'https://s3.{region}.amazonaws.com',
                config=config
            )
            
            # Validate bucket access on initialization
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.info(f"S3 storage initialized: bucket={bucket_name}, region={region}")
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == '404':
                    raise Exception(f"S3 bucket '{bucket_name}' does not exist in region {region}")
                elif error_code == '403':
                    raise Exception(f"Access denied to S3 bucket '{bucket_name}'. Check IAM permissions.")
                else:
                    raise Exception(f"Cannot access S3 bucket '{bucket_name}': {error_code}")
                    
        except NoCredentialsError:
            logger.error("AWS credentials not found. Ensure IAM instance profile is attached to EC2.")
            raise Exception(
                "AWS credentials not configured. "
                "For EC2: Attach IAM instance profile. "
                "For local: Configure AWS CLI with 'aws configure'."
            )
        except ImportError as e:
            logger.error(f"Failed to import boto3: {e}")
            raise Exception("boto3 not installed. Run: pip install boto3")
        except Exception as e:
            logger.error(f"Failed to initialize S3 storage: {e}", exc_info=True)
            raise

    def save_file(self, local_path: Path, remote_name: str) -> str:
        s3_key = f"videos/{remote_name}"
        logger.info(f"Uploading {local_path} to s3://{self.bucket_name}/{s3_key}")
        
        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                self.s3_client.upload_file(
                    str(local_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={'ContentType': 'video/mp4'}
                )
                logger.info(f"Successfully uploaded to S3: {s3_key}")
                break
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Upload attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to upload to S3 after {max_retries} attempts: {e}")
                    raise Exception(f"S3 upload failed: {e}")
        
        # Clean up local file after successful upload
        try:
            local_path.unlink()
            logger.info(f"Removed local file after S3 upload: {local_path}")
        except Exception as e:
            logger.warning(f"Could not remove local file: {e}")
        
        return self.get_file_url(remote_name)

    def get_file_url(self, filename: str) -> str:
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/videos/{filename}"

    def file_exists(self, filename: str) -> bool:
        s3_key = f"videos/{filename}"
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception:
            return False

    def get_download_dir(self) -> Path:
        return self._local_temp_dir


def get_storage_backend() -> StorageBackend:
    from config import settings
    
    if settings.USE_S3 and settings.S3_BUCKET_NAME:
        logger.info("Using S3 storage backend")
        return S3Storage(
            bucket_name=settings.S3_BUCKET_NAME,
            region=settings.AWS_REGION
        )
    else:
        logger.info("Using local storage backend")
        return LocalStorage(download_dir=settings.LOCAL_DOWNLOAD_DIR)
