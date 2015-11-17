from boto import connect_s3
from boto.exception import S3ResponseError
from boto.s3.key import Key
from config.security import S3_BUCKET
from libs import encryption, logging

from config.security import AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID

CONN = connect_s3(aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)


def _get_bucket(name):
    """ Method tries to get a bucket; returns None if bucket doesn't exist """
    try:
        bucket = CONN.get_bucket(name)
        return bucket
    except S3ResponseError as e:
        logging.log_error(e, e.message)
        return None

# def s3_upload_raw( key_name, some_string ):
#     """ Method uploads string to bucket with key_name"""
#     bucket = _get_bucket(S3_BUCKET)
#     key = bucket.new_key(key_name)
#     key.set_contents_from_string(some_string)

def s3_upload( key_path, data_string, study_id, raw_path=False):
    """ Uploads data to s3, ensures data is encrypted with the key from the
        provided study.  Takes an optional argument, raw_path, which defaults to
        false.  When false the study_id is prepended to the S3 file path (key_path),
        placing the file in the appropriate study folder. """
    if not raw_path: key_path = str(study_id) + "/" + key_path
    data = encryption.encrypt_for_server(data_string, study_id)
    key = _get_bucket(S3_BUCKET).new_key(key_path)
    key.set_contents_from_string(data)

# def s3_retrieve_raw( key_name ):
#     """ Method returns file contents with specified S3 key path"""
#     key = Key(_get_bucket(S3_BUCKET), key_name)
#     return key.read()

def s3_retrieve(key_path, study_id, raw_path=False):
    """ Takes an S3 file path (key_path), and a study ID.  Takes an optional
        argument, raw_path, which defaults to false.  When set to false the 
        path is prepended to place the file in the appropriate study_id  folder. """
    if not raw_path: key_path = str(study_id) + "/" + key_path
    key = Key(_get_bucket(S3_BUCKET), key_path)
    return encryption.decrypt_server( key.read(), study_id )

# def s3_retrieve_or_none(key_path, study_id, raw_path=False):
#     """ Like s3_retreive except returns None if the key does not exist instead
#         of erroring.  This API makes an additional network request, increasing
#         cost and latency. """
#     if not raw_path: key_path = str(study_id) + "/" + key_path
#     key = _get_bucket(S3_BUCKET).get_key(key_path) #this line is the only difference.
#     if not key: return None
#     return encryption.decrypt_server(key.read(), study_id)

def s3_list_files( prefix ):
    """ Method fetches a list of filenames with prefix.
        note: entering the empty string into this search without later calling
        the object results in a truncated/paginated view."""
    bucket = _get_bucket(S3_BUCKET)
    results = bucket.list(prefix=prefix)
    return [i.name.strip("/") for i in results]

def s3_delete(key_path):
    key = Key(_get_bucket(S3_BUCKET), key_path)
    key.delete()

#unused file based upload function, not up to date with new upload file names.
# def s3_upload_handler_file( key_name, file_obj ):
#     """ Method uploads file object to bucket with key_name"""
#     bucket = _get_bucket(S3_BUCKET)
#     key = bucket.new_key(key_name)
#     key.set_metadata('Content-Type', mimetypes.guess_type(key_name))
#     # seek to the beginning of the file and read it into the key
#     file_obj.seek(0)
#     key.set_contents_from_file(file_obj)

################################################################################
######################### Client Key Management ################################
################################################################################

def create_client_key_pair(patient_id, study_id):
    """Generate key pairing, push to database, return sanitized key for client."""
    public, private = encryption.generate_key_pairing()
    s3_upload( "keys/" + patient_id + "_private", private, study_id )
    s3_upload( "keys/" + patient_id + "_public", public, study_id )


def get_client_public_key_string(patient_id, study_id):
    """Grabs a user's public key string from s3."""
    key_string = s3_retrieve( "keys/" + patient_id +"_public" , study_id)
    return encryption.prepare_X509_key_for_java( key_string )


def get_client_public_key(patient_id, study_id):
    """Grabs a user's public key file from s3."""
    key = s3_retrieve( "keys/" + patient_id +"_public", study_id )
    return encryption.import_RSA_key( key )


def get_client_private_key(patient_id, study_id):
    """Grabs a user's private key file from s3."""
    key = s3_retrieve( "keys/" + patient_id +"_private", study_id)
    return encryption.import_RSA_key( key )
