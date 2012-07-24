import mimetypes
import os

try:
    from boto.s3.connection import S3Connection, SubdomainCallingFormat
    from boto.exception import S3ResponseError, S3CreateError
    from boto.s3.key import Key
except ImportError:
    raise RuntimeError("Could not load Boto's S3 bindings.\n"
                       "See http://code.google.com/p/boto/")

from flask import current_app

from .base import Storage, StorageException


def safe_join(base, *paths):
    """
    A version of django.utils._os.safe_join for S3 paths.

    Joins one or more path components to the base path component
    intelligently. Returns a normalized version of the final path.

    The final path must be located inside of the base path component
    (otherwise a ValueError is raised).

    Paths outside the base path indicate a possible security
    sensitive operation.
    """
    from urlparse import urljoin
    #base_path = force_unicode(base)
    base_path = unicode(base)
    base_path = base_path.rstrip('/')
    paths = [unicode(p) for p in paths]

    final_path = base_path
    for path in paths:
        final_path = urljoin(final_path.rstrip('/') + "/", path.rstrip("/"))

    # Ensure final_path starts with base_path and that the next character after
    # the final path is '/' (or nothing, in which case final_path must be
    # equal to base_path).
    base_path_len = len(base_path)
    if not final_path.startswith(base_path) \
            or final_path[base_path_len:base_path_len + 1] not in ('', '/'):
        raise ValueError('the joined path is located outside of the base path'
                         ' component')

    return final_path.lstrip('/')


class S3BotoStorage(Storage):
    def __init__(
            self,
            folder_name=None,
            access_key=None,
            secret_key=None,
            bucket_acl=None,
            acl=None,
            headers=None,
            gzip=None,
            gzip_content_types=None,
            querystring_auth=None,
            querystring_expire=None,
            reduced_redundancy=None,
            custom_domain=None,
            secure_urls=None,
            location=None,
            file_name_charset=None,
            preload_metadata=None,
            calling_format=None,
            file_overwrite=None,
            auto_create_bucket=None):

        access_key = access_key or \
            current_app.config.get('AWS_ACCESS_KEY_ID', None)
        secret_key = secret_key or \
            current_app.config.get('AWS_SECRET_ACCESS_KEY', None)
        calling_format = calling_format or \
            current_app.config.get(
                'AWS_S3_CALLING_FORMAT',
                SubdomainCallingFormat()
            )
        self.auto_create_bucket = auto_create_bucket or \
            current_app.config.get('AWS_AUTO_CREATE_BUCKET', False)
        self.bucket_name = folder_name or \
            current_app.config.get('AWS_STORAGE_BUCKET_NAME', None)
        self.acl = acl or \
            current_app.config.get('AWS_DEFAULT_ACL', 'public-read')
        self.bucket_acl = bucket_acl or \
            current_app.config.get('AWS_BUCKET_ACL', self.acl)
        self.file_overwrite = file_overwrite or \
            current_app.config.get('AWS_S3_FILE_OVERWRITE', False)
        self.headers = headers or \
            current_app.config.get('AWS_HEADERS', {})
        self.preload_metadata = preload_metadata or \
            current_app.config.get('AWS_PRELOAD_METADATA', False)
        self.gzip = gzip or \
            current_app.config.get('AWS_IS_GZIPPED', False)
        self.gzip_content_types = gzip_content_types or \
            current_app.config.get(
                'GZIP_CONTENT_TYPES', (
                    'text/css',
                    'application/javascript',
                    'application/x-javascript',
                )
            )
        self.querystring_auth = querystring_auth or \
            current_app.config.get('AWS_QUERYSTRING_AUTH', True)
        self.querystring_expire = querystring_expire or \
            current_app.config.get('AWS_QUERYSTRING_EXPIRE', 3600)
        self.reduced_redundancy = reduced_redundancy or \
            current_app.config.get('AWS_REDUCED_REDUNDANCY', False)
        self.custom_domain = custom_domain or \
            current_app.config.get('AWS_S3_CUSTOM_DOMAIN', None)
        self.secure_urls = secure_urls or \
            current_app.config.get('AWS_S3_SECURE_URLS', True)
        self.location = location or current_app.config.get('AWS_LOCATION', '')
        self.location = self.location.lstrip('/')
        self.file_name_charset = file_name_charset or \
            current_app.config.get('AWS_S3_FILE_NAME_CHARSET', 'utf-8')

        self.connection = S3Connection(
            access_key, secret_key,
            calling_format=calling_format
        )
        self._entries = {}

    @property
    def folder_name(self):
        return self.bucket_name

    @property
    def bucket(self):
        """
        Get the current bucket. If there is no current bucket object
        create it.
        """
        if not hasattr(self, '_bucket'):
            self._bucket = self._get_or_create_bucket(self.bucket_name)
        return self._bucket

    def get_all_folders(self):
        return self.connection.get_all_buckets()

    @property
    def folder(self):
        return self.bucket

    @property
    def files(self):
        return [
            S3BotoStorageFile(self, key.name) for key in self.bucket.list()
        ]

    def create_folder(self, name=None):
        if not name:
            name = self.folder_name
        try:
            bucket = self.connection.create_bucket(name)
            bucket.set_acl(self.bucket_acl)
        except S3CreateError as e:
            raise StorageException(e.status)
        return bucket

    def _get_or_create_bucket(self, name):
        """Retrieves a bucket if it exists, otherwise creates it."""
        try:
            return self.connection.get_bucket(
                name,
                validate=self.auto_create_bucket
            )
        except S3ResponseError:
            if self.auto_create_bucket:
                bucket = self.connection.create_bucket(name)
                bucket.set_acl(self.bucket_acl)
                return bucket
            raise RuntimeError(
                "Bucket specified by "
                "S3_BUCKET_NAME does not exist. "
                "Buckets can be automatically created by setting "
                "AWS_AUTO_CREATE_BUCKET=True")

    def _clean_name(self, name):
        """
        Cleans the name so that Windows style paths work
        """
        # Useful for windows' paths
        return os.path.normpath(name).replace('\\', '/')

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like
        /path/to/ignored/../something.txt
        work. We check to make sure that the path pointed to is not outside
        the directory specified by the LOCATION setting.
        """
        try:
            return safe_join(self.location, name)
        except ValueError:
            raise RuntimeError("Attempted access to '%s' denied." % name)

    def _encode_name(self, name):
        return str(name)
        #return smart_str(name, encoding=self.file_name_charset)

    def _decode_name(self, name):
        return unicode(name)
        #return force_unicode(name, encoding=self.file_name_charset)

    def _save(self, name, content):
        cleaned_name = self._clean_name(name)
        name = self._normalize_name(cleaned_name)
        headers = self.headers.copy()
        content_type = getattr(
            content,
            'content_type',
            mimetypes.guess_type(name)[0] or Key.DefaultContentType
        )
        content.name = cleaned_name
        encoded_name = self._encode_name(name)
        key = self.bucket.get_key(encoded_name)
        if not key:
            key = self.bucket.new_key(encoded_name)
        if self.preload_metadata:
            self._entries[encoded_name] = key

        key.set_metadata('Content-Type', content_type)
        key.set_contents_from_file(
            content,
            headers=headers,
            policy=self.acl,
            reduced_redundancy=self.reduced_redundancy
        )
        return cleaned_name

    def _open(self, name, mode='rb'):
        return S3BotoStorageFile(self, name)

    def delete(self):
        self.bucket.delete()

    def exists(self, name):
        name = self._normalize_name(self._clean_name(name))
        return bool(self.bucket.lookup(self._encode_name(name)))

    def url(self, name):
        name = self._normalize_name(self._clean_name(name))

        if self.custom_domain:
            return "%s://%s/%s" % ('https' if self.secure_urls else 'http',
                                   self.custom_domain, name)
        return self.connection.generate_url(
            self.querystring_expire,
            method='GET',
            bucket=self.bucket.name,
            key=self._encode_name(name),
            query_auth=self.querystring_auth,
            force_http=not self.secure_urls
        )


class S3BotoStorageFile(object):
    def __init__(self, storage, name):
        self._storage = storage
        self._key = Key(storage.bucket)
        self._key.name = name
        self._file = self._key
        self._pos = 0

    @property
    def name(self):
        return self._key.name

    @property
    def url(self):
        return self._storage.url(self._key.name)

    def delete(self):
        name = self._storage._normalize_name(
            self._storage._clean_name(self._key.name)
        )
        self._storage.bucket.delete_key(self._storage._encode_name(name))

    @property
    def size(self):
        return self._file.size

    def read(self, size=None):
        if self._pos == self.size:
            return ''
        size = min(size, self.size - self._pos)
        data = self._file.read(size=size or -1, offset=self._pos)
        self._pos += len(data)
        return data

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self._pos = offset
        elif whence == os.SEEK_CUR:
            self._pos += offset
        elif whence == os.SEEK_END:
            self._pos = self.size + offset
        else:
            raise IOError(22, 'Invalid argument')

    def tell(self):
        return self._pos
