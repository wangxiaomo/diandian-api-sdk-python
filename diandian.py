#-*- coding: utf-8 -*-

__version__ = '1.0'
__author__  = 'xiaomo(wxm4ever@gmail.com)'

try:
    import json
except ImportError:
    import simplejson as json
import time
import urllib, urllib2
import logging


def _encode_params(**kw):
    """
    Encode parameters
    """
    args = []
    for k,v in kw.iteritems():
        qv = v.encode('utf-8') if isinstance(v, unicode) else str(v)
        args.append('%s=%s' % (k, urllib.quote(qv)))
    return '&'.join(args)

def _encode_multipart(**kw):
    undary = '----------%s' % hex(int(time.time() * 1000))
    data = []
    for k, v in kw.iteritems():
        data.append('--%s' % boundary)
        if hasattr(v, 'read'):
            # file-like object:
            ext = ''
            filename = getattr(v, 'name', '') 
            n = filename.rfind('.')
            if n != (-1):
                ext = filename[n:].lower()
            content = v.read()
            data.append('Content-Disposition: form-data; name="%s"; filename="hidden"' % k)
            data.append('Content-Length: %d' % len(content))
            data.append('Content-Type: %s\r\n' % _guess_content_type(ext))
            data.append(content)
        else:
            data.append('Content-Disposition: form-data; name="%s"\r\n' % k)
            data.append(v.encode('utf-8') if isinstance(v, unicode) else v)
    data.append('--%s--\r\n' % boundary)
    return '\r\n'.join(data), boundary

_CONTENT_TYPES = { '.png': 'image/png', '.gif': 'image/gif', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.jpe': 'image/jpeg' }

def _guess_content_type(ext):
    return _CONTENT_TYPES.get(ext, 'application/octet-stream')

class JsonObject(dict):
    def __getattr__(self, attr):
        return self[attr]
    def __setattr__(self, attr, value):
        self[attr] = value

def _obj_hook(pairs):
    o = JsonObject()
    for k, v in pairs.iteritems():
        o[str(k)] = v
    return o

_HTTP_GET    = 0
_HTTP_POST   = 1
_HTTP_UPLOAD = 2

def _http_get(url, authorization=None, **kw):
    logging.info('GET %s' % url)
    return _http_call(url, _HTTP_GET, authorization, **kw)

def _http_post(url, authorization=None, **kw):
    logging.info('POST %s' % url)
    return _http_call(url, _HTTP_POST, authorization, **kw)

def _http_upload(url, authorization=None, **kw):
    logging.info('MULTIPART POST %s' % url)
    return _http_call(url, _HTTP_UPLOAD, authorization, **kw)

def _http_call(url, method, authorization, **kw):
    params = None
    boundary = None
    if method == _HTTP_UPLOAD:
        params, boundary = _encode_multipart(**kw)
    else:
        params = _encode_params(**kw)
    http_url = '%s?%s' % (url, params) if method == _HTTP_GET else url
    http_body = None if method == _HTTP_GET else params
    http_url = http_url+"access_token=%s" % authorization
    req = urllib2.Request(http_url, data=http_body)
    """
    if authorization:
        req.add_header('Authorization', 'OAuth2 %s' % authorization)
    """
    if boundary:
        req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
    resp = urllib2.urlopen(req)
    body = resp.read()
    r = json.loads(body, object_hook=_obj_hook)
    return r

class APIError(StandardError):
    """
    raise APIError
    """
    def __init__(self, error_code, error, request):
        self.error_code = error_code
        self.error = error
        self.request = request
        StandardError.__init__(self, error)

    def __str__(self):
        return "APIError: %s:%s, request:%s" % (
            self.error_code,
            self.error,
            self.request
        )

    __repr__ = __str__


class HttpObject(object):
    def __init__(self, client, method):
        self.client = client
        self.method = method

    def __getattr__(self, attr):
        def wrap(**kw):
            if self.client.is_expires():
                raise APIError('21327', 'expired_token', attr)
            return _http_call('%s%s' % (self.client.api_url, attr.replace('__', '/')), self.method, self.client.access_token, **kw)
        return wrap


class APIClient(object):
    """
    APIClient using synchronized invocation
    """
    def __init__(self, app_key, app_secret, redirect_uri=None, response_type='code', domain='api.diandian.com', version='2'):
        self.client_id = app_key
        self.client_secret = app_secret
        self.redirect_uri = redirect_uri
        self.response_type = response_type
        self.auth_url = "https://%s/oauth/" % domain
        self.api_url = "https://%s/v1/" % domain
        self.access_token = None
        self.expires = 0.0
        self.get = HttpObject(self, _HTTP_GET)
        self.post = HttpObject(self, _HTTP_POST)
        self.upload = HttpObject(self, _HTTP_UPLOAD)

    def get_authorize_url(self, redirect_uri=None):
        redirect_uri = redirect_uri if redirect_uri else self.redirect_uri
        if not redirect_uri:
            raise APIError('21305', 'Parameter absent: redirect_uri', 'OAuth2 request')
        return '%s%s?%s' % (
            self.auth_url,
            'authorize',
            _encode_params(
                client_id = self.client_id,
                response_type = self.response_type,
                scope = 'read,write'
            )
        )

    def set_access_token(self, access_token, expires_in):
        self.access_token = str(access_token)
        self.expires = float(expires_in)

    def request_access_token(self, code, redirect_uri=None):
        redirect_uri = redirect_uri if redirect_uri else self.redirect_uri
        if not redirect_uri:
            raise APIError('21305', 'Parameter absent: redirect_uri', 'OAuth2 request')
        r = _http_post('%s%s' % (self.auth_url, 'token'),  \
                       client_id = self.client_id,         \
                       client_secret = self.client_secret, \
                       redirect_uri = self.redirect_uri,   \
                       code = code,                        \
                       grant_type = 'authorization_code'
        )
        r.expires_in += int(time.time())
        return r

    def is_expires(self):
        return not self.access_token or time.time()>self.expires

    def __getattr__(self, attr):
        return getattr(self.get, attr)


if __name__ == '__main__':
    app_key = 'nDpH7C7zy2'
    app_secret = 'bcigFfZMVmc0Ax69siZJp9GnRY0SPYs6aa4M'
    callback_uri = 'http://pyxiaomo.sinaapp.com/callback'
    access_token = 'xxx'
    expires_in = 1337816659

    client = APIClient(app_key, app_secret, callback_uri)
    client.set_access_token(access_token, expires_in)
    r = client.get.user__likes()
    print r
