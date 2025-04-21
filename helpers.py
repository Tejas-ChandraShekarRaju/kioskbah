from flask import current_app
from urllib.parse import urlparse

def send_to_s3(file, bucket_name, filename, acl="public-read", content_type=''):
    try:
        if content_type == '':
            content_type = file.content_type
        res = current_app.s3.upload_fileobj(
            file,
            bucket_name,
            filename,
            ExtraArgs={
                "ACL": acl,
                "ContentType": content_type  # Set appropriate content type as per the file
            }
        )
        print(res)
    except Exception as e:
        print("Something Happened: ", e)
        return str(e)
    return 'success'

def delete_from_s3(file_path):
    try:
        # Parse the URL to get the object key
        parsed_url = urlparse(file_path)
        object_key = parsed_url.path.lstrip('/')
        
        # Delete the object from S3
        current_app.s3.delete_object(
            Bucket=current_app.config['S3_BUCKET'],
            Key=object_key
        )
        return 'success'
    except Exception as e:
        print("Error deleting from S3:", e)
        return str(e)

def allowed_file(filename):
    allowed = '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
    if not allowed:
        print(f"File extension not allowed: {filename.rsplit('.', 1)[1].lower() if '.' in filename else 'no extension'}")
    return allowed 