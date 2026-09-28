import os
import boto3
from django.conf import settings
from botocore.client import Config

def generate_presigned_upload_url(storage_key, expiration=3600):
    # Determine the public endpoint for the browser to use (usually localhost:9000 for local dev)
    public_endpoint = os.getenv('MINIO_PUBLIC_ENDPOINT', 'http://127.0.0.1:9000')
    
    s3_client_public = boto3.client(
        's3',
        endpoint_url=public_endpoint,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    url = s3_client_public.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings.MINIO_BUCKET_NAME,
            'Key': storage_key
        },
        ExpiresIn=expiration
    )
    return url

def download_artifact(storage_key, dest_path):
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    s3_client.download_file(settings.MINIO_BUCKET_NAME, storage_key, dest_path)

def delete_artifact(storage_key):
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    s3_client.delete_object(Bucket=settings.MINIO_BUCKET_NAME, Key=storage_key)
