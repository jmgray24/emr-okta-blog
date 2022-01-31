import urllib
import urllib.request
import urllib.parse
from crhelper import CfnResource
import zipfile 
from datetime import *
from io import BytesIO
import sys
from pip._internal import main

main(['install', '-I', '-q', 'boto3', '--target', '/tmp/', '--no-cache-dir', '--disable-pip-version-check'])
sys.path.insert(0,'/tmp/')

import boto3
from botocore.exceptions import ClientError

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
    with urllib.request.urlopen('https://emr-okta-blog.s3.amazonaws.com/data/cities.zip') as f:
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

def setup_lf_perms(lf,sts):
    print('Enabling Lake Formations perms...')
    lf_settings = lf.get_data_lake_settings()['DataLakeSettings']
    lf_settings['CreateDatabaseDefaultPermissions'] = []
    lf_settings['CreateTableDefaultPermissions'] = []
    lf_settings['AllowExternalDataFiltering'] = True
    lf_settings['ExternalDataFilteringAllowList'] = [{'DataLakePrincipalIdentifier': sts.get_caller_identity().get('Account')}]
    lf.put_data_lake_settings(DataLakeSettings=lf_settings)
    print('Successfully enabled Lake Formation perms!')

def handler(event, context):
    print(boto3.__version__)
    helper(event, context)

@helper.create
def create(event, context):
    s3 = boto3.resource('s3')
    s3Client = boto3.client('s3')
    iam = boto3.client('iam')
    sts = boto3.client('sts')
    lf = boto3.client('lakeformation')
    setup_lf_perms(lf,sts)
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
