import os
import gzip
import cgi
from StringIO import StringIO
from datetime import datetime


class HttpRoot:
    """
    A root middleware object that creates the :class:`HttpContext` and dispatches it to other registered middleware
    """

    def __init__(self, stack=[]):
        self.stack = stack

    def add(self, middleware):
        """
        Pushes the middleware onto the stack
        """
        self.stack.append(middleware)

    def dispatch(self, env, start_response):
        """
        Dispatches the WSGI request
        """
        context = HttpContext(env, start_response)
        for middleware in self.stack:
            output = middleware.handle(context)
            if context.response_ready:
                return output


class HttpContext:
    """
    Instance of :class:`HttpContext` is passed to all HTTP handler methods

    .. attribute:: env

        WSGI environment dict

    .. attribute:: path

        Path segment of the URL

    .. attribute:: headers

        List of HTTP response headers

    .. attribute:: response_ready

        Indicates whether a HTTP response has already been submitted in this context

    .. attribute:: query

        HTTP query parameters
    """

    def __init__(self, env, start_response):
        self.start_response = start_response
        self.env = env
        self.path = env['PATH_INFO']
        self.headers = []
        self.response_ready = False

        self.env.setdefault('QUERY_STRING', '')
        if self.env['REQUEST_METHOD'].upper() == 'POST':
            ctype = self.env.get('CONTENT_TYPE', 'application/x-www-form-urlencoded')
            if ctype.startswith('application/x-www-form-urlencoded') \
               or ctype.startswith('multipart/form-data'):
                self.query = cgi.FieldStorage(fp=self.env['wsgi.input'],
                                       environ=self.env,
                                       keep_blank_values=1)
        else:
            self.query = cgi.FieldStorage(environ=self.env, keep_blank_values=1)

    def add_header(self, key, value):
        """
        Adds a given HTTP header to the response
        """
        self.headers += [(key, value)]

    def remove_header(self, key):
        """
        Removed a given HTTP header from the response
        """
        for k in self.headers:
            if k == key:
                del self.headers[key]

    def fallthrough(self, handler):
        """
        Executes a ``handler`` in this context

        :returns: handler-supplied output
        """
        return handler.handle(self)

    def respond(self, status):
        """
        Creates a response with given HTTP status line
        """
        self.start_response(status, self.headers)
        self.response_ready = True

    def respond_ok(self):
        """
        Creates a ``HTTP 200 OK`` response
        """
        self.respond('200 OK')

    def respond_server_error(self):
        """
        Returns a HTTP ``500 Server Error`` response
        """
        self.respond('500 Server Error')
        return 'Server Error'

    def respond_forbidden(self):
        """
        Returns a HTTP ``403 Forbidden`` response
        """
        self.respond('403 Forbidden')
        return 'Forbidden'

    def respond_not_found(self):
        """
        Returns a ``HTTP 404 Not Found`` response
        """
        self.respond('404 Not Found')
        return 'Not Found'

    def redirect(self, url):
        """
        Returns a ``HTTP 302 Found`` redirect response with given ``url``
        """
        self.add_header('Location', url)
        self.respond('302 Found')
        return ''

    def gzip(self, content):
        """
        Returns a GZip compressed response with given ``content`` and correct headers
        """
        io = StringIO()
        gz = gzip.GzipFile('', 'wb', 9, io)
        gz.write(content)
        gz.close()
        compressed = io.getvalue()

        self.add_header('Content-Length', str(len(compressed)))
        self.add_header('Content-Encoding', 'gzip')
        self.respond_ok()

        return compressed

    def file(self, path):
        """
        Returns a GZip compressed response with content of file located in ``path`` and correct headers
        """

        if '..' in path:
            self.respond_forbidden()
            return ''

        if not os.path.isfile(path):
            self.respond_not_found()
            return ''

        content_types = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.woff': 'application/x-font-woff',
        }

        ext = os.path.splitext(path)[1]
        if ext in content_types:
            self.add_header('Content-Type', content_types[ext])
        else:
            self.add_header('Content-Type', 'application/octet-stream')

        mtime = datetime.utcfromtimestamp(os.path.getmtime(path))

        rtime = self.env.get('HTTP_IF_MODIFIED_SINCE', None)
        if rtime is not None:
            try:
                rtime = datetime.strptime(rtime, '%a, %b %d %Y %H:%M:%S GMT')
                if mtime <= rtime:
                    self.respond('304 Not Modified')
                    return ''
            except:
                pass

        #self.add_header('Content-Length', str(size))
        self.add_header('Last-Modified', mtime.strftime('%a, %b %d %Y %H:%M:%S GMT'))
        return self.gzip(open(path).read())


class HttpHandler (object):
    """
    Base class for everything that can process HTTP requests
    """

    def handle(self, context):
        """
        Should create a HTTP response in the given ``context`` and return the plain output
        """
        pass
