"""Create or update the FailureLab Cognito user without logging its password."""
import os
import boto3

client = boto3.client("cognito-idp", region_name=os.getenv("AWS_REGION", "ap-south-1"))
pool = os.environ["USER_POOL_ID"]
email = os.environ["USER_EMAIL"]
password = os.environ["USER_PASSWORD"]
try:
    client.admin_create_user(
        UserPoolId=pool,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
        MessageAction="SUPPRESS",
    )
except client.exceptions.UsernameExistsException:
    pass

client.admin_set_user_password(
    UserPoolId=pool,
    Username=email,
    Password=password,
    Permanent=True,
)
print(f"Cognito user is ready: {email}")
