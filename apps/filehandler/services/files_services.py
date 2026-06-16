from os import path
import boto3,re
from django.conf import settings
from pathlib import Path

class FilesActions:
    @staticmethod
    def extract_day_from_key(key: str) -> int | None:
        media_type = key.split("/")[-2]
        m = re.search(r"/day-(\d+)/", key)
        if not m:
            return None,None
        return int(m.group(1)),media_type
    
    @staticmethod
    def get_assessment_files(request,prefix):
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            file_urls = []

            continuation_token = None
            while True:
                if continuation_token:
                    response = s3_client.list_objects_v2(
                        Bucket=bucket_name,
                        Prefix=prefix,
                        ContinuationToken=continuation_token,
                    )
                else:
                    response = s3_client.list_objects_v2(
                        Bucket=bucket_name,
                        Prefix=prefix,
                    )

                if "Contents" in response:
                    for obj in response["Contents"]:
                        key = obj["Key"]
                        if key.endswith("/"):  # Skip directories
                            continue
                        
                        url = s3_client.generate_presigned_url(
                            "get_object",
                            Params={"Bucket": bucket_name, "Key": key},
                            ExpiresIn=3600,
                        )
                        file_urls.append(url)
                
                if response.get("IsTruncated"):
                    continuation_token = response.get("NextContinuationToken")
                else:
                    break
            
            return file_urls
            
        except Exception as e:
            return []

    @staticmethod
    def get_management_files(request,prefixes):
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            file_urls = []

            for prefix in prefixes:
                continuation_token = None

                while True:
                    if continuation_token:
                        response = s3_client.list_objects_v2(
                            Bucket=bucket_name,
                            Prefix=prefix,
                            ContinuationToken=continuation_token,
                        )
                    else:
                        response = s3_client.list_objects_v2(
                            Bucket=bucket_name,
                            Prefix=prefix,
                        )


                    if "Contents" in response:
                        for obj in response["Contents"]:
                            key = obj["Key"]
                            day, media_type = FilesActions.extract_day_from_key(key)
                            if key.endswith("/"):
                                continue

                            url = s3_client.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": bucket_name, "Key": key},
                                ExpiresIn=3600,
                            )
                            file_urls.append(
                                {
                                    "key": key,
                                    "url": url,
                                    "day": day,
                                    "media_type": media_type,
                                }
                            )

                    if response.get("IsTruncated"):
                        continuation_token = response.get("NextContinuationToken")
                    else:
                        break

            return file_urls
            
        except Exception as e:
            return []


    @staticmethod
    def save_feedback(request):
        try:
            feedback_data = request.data.get('feedback', None)
            
            return 
            
        except Exception as e:
            pass
