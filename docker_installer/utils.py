import urllib2
import paramiko
import httplib
import os
import errno

def is_host_can_access_docker():
    docker_url = "download.docker.com"
    conn = httplib.HTTPConnection(docker_url, timeout=5)
    try:
        conn.request("HEAD", "/")
        conn.close()
        # log.info("Host can access {0}".format(docker_url))
        return True
    except Exception:
        conn.close()
        # log.info("Host can not access {0}".format(docker_url))
        return False

def get_remote_content_size(url):
    request = urllib2.Request(url)
    request.get_method = lambda : 'HEAD'
    response = urllib2.urlopen(request)
    return int(response.info()["Content-Length"])

def createSSHClient(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
# def install_opener():
#     opener = urllib2.build_opener(
#         urllib2.HTTPHandler(),
#         urllib2.HTTPSHandler(
#             # context=ssl.SSLContext(ssl.PROTOCOL_SSLv23) #context=ssl.SSLContext(ssl.PROTOCOL_SSLv23)
#         # ,
#         # urllib2.ProxyHandler(
#         #     {
#         #         'https': 'http://user:pass@108.61.161.136:8388',
#         #         'http': 'http://user:pass@108.61.161.136:8388'
#         #     }
#         # )
#     ))
#     urllib2.install_opener(opener)

# install_opener()