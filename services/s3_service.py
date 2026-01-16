# import boto3
# import mimetypes
# from config import settings
# from botocore.exceptions import ClientError
# from fastapi.concurrency import run_in_threadpool

# # Initialize S3 client (sync client, used safely via threadpool)
# s3_client = boto3.client(
#     "s3",
#     aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#     aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#     region_name=settings.AWS_REGION,
# )


# async def upload_to_s3(file_content: bytes, filename: str) -> str:
#     """
#     Upload file to S3 bucket (async-safe)
#     Returns: public S3 URL
#     """
#     content_type, _ = mimetypes.guess_type(filename)

#     try:
#         await run_in_threadpool(
#             s3_client.put_object,
#             Bucket=settings.S3_BUCKET_NAME,
#             Key=filename,
#             Body=file_content,
#             ContentType=content_type or "application/octet-stream",
#         )

#         url = (
#             f"https://{settings.S3_BUCKET_NAME}."
#             f"s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
#         )

#         print(f"✅ File uploaded to S3: {url}")
#         return url

#     except ClientError as e:
#         print(f"❌ S3 Upload Error: {e}")
#         raise Exception("Failed to upload file to S3")


# async def delete_from_s3(filename: str) -> bool:
#     """
#     Delete file from S3 (async-safe)
#     """
#     try:
#         await run_in_threadpool(
#             s3_client.delete_object,
#             Bucket=settings.S3_BUCKET_NAME,
#             Key=filename,
#         )

#         print(f"✅ File deleted from S3: {filename}")
#         return True

#     except ClientError as e:
#         print(f"❌ S3 Delete Error: {e}")
#         return False


# async def get_presigned_url(filename: str, expiration: int = 3600) -> str:
#     """
#     Generate presigned URL for private S3 object (async-safe)
#     """
#     try:
#         url = await run_in_threadpool(
#             s3_client.generate_presigned_url,
#             "get_object",
#             {
#                 "Bucket": settings.S3_BUCKET_NAME,
#                 "Key": filename,
#             },
#             expiration,
#         )
#         return url

#     except ClientError as e:
#         print(f"❌ Presigned URL Error: {e}")
#         raise Exception("Failed to generate presigned URL")






import boto3
import mimetypes
from config import settings
from botocore.exceptions import ClientError
from fastapi.concurrency import run_in_threadpool

# Initialize S3 client (sync client, used safely via threadpool)
s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


async def upload_to_s3(file_content: bytes, filename: str) -> str:
    """
    Upload file to S3 bucket and return presigned URL (async-safe)
    Returns: presigned S3 URL (valid for 7 days)
    """
    content_type, _ = mimetypes.guess_type(filename)

    try:
        # Upload file to S3
        await run_in_threadpool(
            s3_client.put_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=filename,
            Body=file_content,
            ContentType=content_type or "application/octet-stream",
        )

        # Generate presigned URL for the uploaded file
        presigned_url = await get_presigned_url(filename, expiration=604800)  # 7 days
        
        print(f"✅ File uploaded to S3: {filename}")
        return presigned_url

    except ClientError as e:
        print(f"❌ S3 Upload Error: {e}")
        raise Exception("Failed to upload file to S3")


async def delete_from_s3(filename: str) -> bool:
    """
    Delete file from S3 (async-safe)
    """
    try:
        await run_in_threadpool(
            s3_client.delete_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=filename,
        )

        print(f"✅ File deleted from S3: {filename}")
        return True

    except ClientError as e:
        print(f"❌ S3 Delete Error: {e}")
        return False


async def get_presigned_url(filename: str, expiration: int = 3600) -> str:
    """
    Generate presigned URL for private S3 object (async-safe)
    Default expiration: 1 hour (3600 seconds)
    """
    try:
        url = await run_in_threadpool(
            s3_client.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": filename,
            },
            ExpiresIn=expiration,
        )
        return url

    except ClientError as e:
        print(f"❌ Presigned URL Error: {e}")
        raise Exception("Failed to generate presigned URL")


async def upload_public_to_s3(file_content: bytes, filename: str) -> str:
    """
    Upload file to S3 with public-read ACL (requires bucket to allow public access)
    Returns: public S3 URL
    """
    content_type, _ = mimetypes.guess_type(filename)

    try:
        await run_in_threadpool(
            s3_client.put_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=filename,
            Body=file_content,
            ContentType=content_type or "application/octet-stream",
            ACL='public-read'  # Make the object publicly accessible
        )

        url = (
            f"https://{settings.S3_BUCKET_NAME}."
            f"s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
        )

        print(f"✅ File uploaded to S3 (public): {url}")
        return url

    except ClientError as e:
        print(f"❌ S3 Upload Error: {e}")
        raise Exception("Failed to upload file to S3")