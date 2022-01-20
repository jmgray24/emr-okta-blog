import urllib
import urllib.request
import boto3
import urllib.parse
from crhelper import CfnResource
import zipfile 
from datetime import *
from io import BytesIO

helper = CfnResource(
	json_logging=False,
	log_level='DEBUG', 
	boto_level='CRITICAL'
)

def create_saml_idp(s3, iam, dataBucketName, samlProviderName, oktaAppMetadataURL):
    print('Fetching SAML metadata...')
    with urllib.request.urlopen(oktaAppMetadataURL) as f:
        file_content = f.read()
    print('Writing SAML metadata to S3...')
    s3.Bucket(dataBucketName).put_object(Key='IdP-metadata/okta-metadata.xml', Body=file_content)
    print('Creating SAML provider entry...')
    response = iam.create_saml_provider(SAMLMetadataDocument=file_content.decode('utf-8'), Name=samlProviderName)
    print('Successfully created SAML provider: '+response['SAMLProviderArn'])
    return response['SAMLProviderArn']

def upload_data(s3Client,dataBucketName): 
    with urllib.request.urlopen('https://emr-okta-blog.s3.amazonaws.com/data/cars.zip') as f:
        file_content = f.read()
    print('Unzipping archive...')
    z = zipfile.ZipFile(BytesIO(file_content)) 
    for filename in z.namelist(): 
        print('Uploading file: '+filename)
        s3Client.put_object(
            Body=z.open(filename).read(),
            Bucket=dataBucketName,
            Key='Data/'+filename
        )
    print('File upload complete!')

def handler(event, context):
    helper(event, context)

@helper.create
def create(event, context):
    s3 = boto3.resource('s3')
    s3Client = boto3.client('s3')
    iam = boto3.client('iam')
    helper.Data['SAMLProviderArn'] = create_saml_idp(s3, iam, event['ResourceProperties']['DataBucketName'], event['ResourceProperties']['SAMLProviderName'], event['ResourceProperties']['OktaAppMetadataURL'])
    upload_data(s3Client,event['ResourceProperties']['DataBucketName'])

@helper.update  
def update(event, context):
    #todo
    return
    
@helper.delete
def delete(event, context):
    print('Delete initiated')
    s3 = boto3.resource('s3')
    iam = boto3.client('iam')
    sts = boto3.client('sts')
    print('Purgung S3 bucket...')
    s3.Bucket(event['ResourceProperties']['DataBucketName']).objects.delete()
    print('Removing SAML provider entry...')
    iam.delete_saml_provider(SAMLProviderArn='arn:aws:iam::' + sts.get_caller_identity().get('Account') + ':saml-provider/' + event['ResourceProperties']['SAMLProviderName'])
    print('Deletion complete!')
