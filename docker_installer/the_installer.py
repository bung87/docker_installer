#-*- coding: utf-8 -*-
#!/usr/bin/env python

from docker_installer.constant import SUPPORTED_ARCH, SUPPORTED_PLATFORM, BASE_DIR_NAME
from docker_installer.utils import is_host_can_access_docker, is_host_can_access_github,get_remote_content_size, createSSHClient, mkdir_p
import sys
import platform
import re
import os
import paramiko
import logging
import scp
from scp import SCPClient
import argparse,textwrap
import socket
if sys.version_info < (3,):
    from urlparse import urlparse,urljoin,urlsplit
    from urllib import urlretrieve
    from urllib2 import urlopen
    from BeautifulSoup import BeautifulSoup
else:
    from urllib.parse import urlparse,urljoin,urlsplit
    from urllib.request import urlretrieve,urlopen
    from bs4 import BeautifulSoup
from functools import partial
import ssl
from functools import wraps
from docker_installer import __version__
from subprocess import Popen,PIPE
# ssl.PROTOCOL_SSLv23 = ssl.PROTOCOL_TLSv1
# log,ssh,loginpassword,HOST_HOME,REMOTE_HOME,processor = None
import shutil
import io

class FakeClient:
    def exec_command(self,s):
        pip = Popen(s, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        output = pip.stdout.read().replace(r"\n","")
        f = io.BytesIO(output)
        log.info("FakeClient:exec_command {0}".format(output))
        return (pip.stdin,f,pip.stderr)

class FakeScpClient:
    def put(self,filepath, recursive, remote_path):
        shutil.copytree(filepath,remote_path)

def init():
    global log, ssh_client, scp_client,loginpassword, HOST_HOME, REMOTE_HOME, system, processor,machine,os_market_name
    log = logging.getLogger(__name__)
    # loglevel = "ERROR"
    loglevel = args.log
    argvlen = len(sys.argv)
    server = args.ip
    port = args.port
    user = args.user
    loginpassword = args.password

    numeric_level = getattr(logging, loglevel.upper(), None)

    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(level=numeric_level)
    port = int(port)
    if args.local:
        ssh_client = FakeClient()
        scp_client = FakeScpClient()
    else:
        ssh_client = createSSHClient(server, port, user, loginpassword)
        scp_client = SCPClient(ssh_client.get_transport(), progress=progress)
    HOST_HOME = os.path.expanduser('~')

    stdin, stdout, stderr = ssh_client.exec_command(
        "export PYTHONIOENCODING=UTF-8;python -c 'import platform;print \"萌\".join(platform.uname())'")

    (system, node, release, version, machine, processor) = stdout.read().decode("utf8").split(u"萌")
    os_detect = os.path.join(os.path.dirname(__file__),"os_detect.py")
    with open(os_detect,"rb") as f:
        content = f.read()
        stdin, stdout, stderr = ssh_client.exec_command("python -c '{0}'".format(content))
        (os_market_name,release) = eval(stdout.read())
   
    processor = processor.strip()
    if not processor:
        processor = machine
    stdin, stdout, stderr = ssh_client.exec_command("echo $HOME")
    REMOTE_HOME = stdout.read().strip()


def sudo(e):
    return "echo {loginpassword} | sudo -S {e}".format(loginpassword=loginpassword, e=e)


def progress(filename, size, sent):
    percent = float(sent) / size
    percent = round(percent * 100, 2)
    if percent > 1:
        log.info("Sent %s %d of %d bytes (%0.2f%%)" %
                (filename, sent, size, percent))


def check_if_docker_installed():
    stdin, stdout, stderr = ssh_client.exec_command("docker -v")
    output = stdout.read()
    groups = re.findall("\d+\.\d+", output)
    if output != ""  and len(groups) != 0 :
        log.info("Target already has docker installed!")
        return True
    return False

def check_if_docker_compose_installed():
    stdin, stdout, stderr = ssh_client.exec_command("docker-compose -v")
    output = stdout.read()
    groups = re.findall("\d+\.\d+", output)
    if output != ""  and len(groups) != 0:
        log.info("Target already has docker-compose installed!")
        return True
    return False

def sshsudo(e):
    stdin, stdout, stderr = ssh_client.exec_command(sudo(e))
    err = stderr.read()
    if err:
        log.error(err)


def host_home(p):
    return os.path.join(HOST_HOME, BASE_DIR_NAME, p)


def remote_home(path):
    return os.path.join(REMOTE_HOME, BASE_DIR_NAME, path)


def ensure_git():
    # https://www.kernel.org/pub/software/scm/git/git-core-0.99.6.tar.gz
    log.info("ensure_git")
    url = "https://www.kernel.org/pub/software/scm/git/"
    response = urlopen(url)
    soup = BeautifulSoup(response)
    regx = re.compile("^git-([0-9\.]+)\.tar\.gz$")
    anchors = soup.findAll('a', text=regx)
    length = len(anchors)
    last = anchors[length - 1]
    try:
        last_href = last["href"]
    except Exception as e:
        last_href = last
    basename = os.path.basename(last_href)
    log.info("latest git version found:{0}".format(basename))
    lastlink = urljoin(url, last_href)
    filepath = host_home(basename)
    extract_dir = os.path.splitext(os.path.splitext(basename)[0])[0]
    ver = regx.match(basename).group(1)

    def callback():
        remote_file_path = remote_home(basename)
        remote_path = os.path.dirname(remote_file_path)
        stdin, stdout, stderr = ssh_client.exec_command("stat -c %s {0}".format(remote_file_path))
        filesize = stdout.read().strip()
        if not int(filesize) == os.path.getsize(filepath):
            scp_client.put(filepath, recursive=True, remote_path=remote_file_path)
        ssh_client.exec_command(
            "cd {0} && tar -xzf {1}".format(remote_path, basename))
        # ensure libssl-dev libcurl-dev(libcurl4-openssl-dev)
        sshsudo(
            "make --directory={0} prefix=/usr && make --directory={0} prefix=/usr install".format(os.path.join(remote_path, extract_dir)) )
    if not os.path.exists(filepath):
        log.info("download git")
        _reporthook = partial(reporthook, callback,filepath)
        urlretrieve(lastlink, filepath, _reporthook)
    else:
        if get_remote_content_size(lastlink) == os.path.getsize(filepath):
            log.info("Host already has git tarball")
            callback()
        else:
            # partial git tarball on host
            pass


def reporthook(callback,filepath, bytes_so_far, chunk_size, total_size):
    percent = float(bytes_so_far) / total_size
    percent = round(percent * 100, 2)
    log.info("Downloaded %s %d of %d bytes (%0.2f%%)" %
             (os.path.basename(filepath),bytes_so_far, total_size, percent))
    if bytes_so_far >= total_size:
        callback()


def install_docker_offline():
    log.info("install_docker_offline")
    url = "https://download.docker.com/linux/static/stable/{arch}/".format(
        arch=processor)
    log.info("Fetch docker download index page:{0}".format(url))
    for i in xrange(3):
        try:
            response = urlopen(url)
        except socket.timeout:
            pass
        except IOError as e:
            log.error(e.strerror)
            ssh_client.close()
            raise e
    soup = BeautifulSoup(response)
    anchors = soup.findAll('a')
    length = len(anchors)
    last = anchors[length - 1]
    last_href = last["href"]
    basename = os.path.basename(last_href)
    log.info("Latest docker version found:{0}".format(basename))
    lastlink = urljoin(url, last_href)
    relpath = urlparse.urlsplit(url).path[1:]
    filepath = host_home(os.path.join(
        "docker", os.path.normpath(relpath), basename))
    remote_file_path = remote_home(basename)
    remote_path = os.path.dirname(remote_file_path)
    stdin, stdout, stderr = ssh_client.exec_command(
        "stat -c %s {0}".format(remote_file_path))
    filesize = stdout.read().strip()

    def callback():
        ssh_client.exec_command("mkdir -p {0}".format(remote_path))
        try:
            scp_client.put(filepath, recursive=True, remote_path=remote_file_path)
        except scp.SCPException as e:
            if e.message == 'Timout waiting for scp response':
                pass
        ssh_client.exec_command(
            "cd {0} && tar -xzf {1}".format(remote_path, basename))
        sshsudo("cp {0}/* /usr/bin/".format(os.path.join(remote_path, "docker")))

    if filesize == "":
        # docker tarball not downloaded on target
        if not os.path.exists(filepath):
            log.info("Host has not docker tarball")
            if not is_host_can_access_docker():
                exit()

            _reporthook = partial(reporthook, callback,filepath)
            mkdir_p(os.path.dirname(filepath))

            # for i in xrange(3):
            try:
                # stat -c %s docker_installer_resource/docker/linux/static/stable/x86_64/docker-17.09.0-ce.tgz
                urlretrieve(lastlink, filepath, _reporthook)
            # except socket.timeout as e:
            #     log.error(e.strerror)
            #     pass
            # except IOError as e:
            #     log.error(e.strerror)
            #     pass
            except Exception as e:
                log.error(e)
                raise e
            # finally:
            #     # urllib.urlcleanup()
            #     # ssh_client.close()
            #     pass

        else:
            if get_remote_content_size(lastlink) == os.path.getsize(filepath):
                log.info("Host already has docker tarball")
                callback()
            else:
                # partial docker tarball on host
                pass
    else:
        if os.path.exists(filepath) and int(filesize) == os.path.getsize(filepath):
            ssh_client.exec_command(
                "cd {0} && tar -xzf {1}".format(remote_path, basename))
            sshsudo(
                "cp {0}/* /usr/bin/".format(os.path.join(remote_path, "docker")))
            return
        else:
            # partial docker tarball on target
            pass




def install_docker_online():
    log.info("install_docker_online")
    if os_market_name == "Ubuntu":
        # https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/
        if processor in SUPPORTED_ARCH[os_market_name]:
            sshsudo("apt-get update")
            sshsudo("""
                apt-get install \
                apt-transport-https \
                ca-certificates \
                curl \
                software-properties-common
                """)

            ssh_client.exec_command(
                "curl -fsSL https://download.docker.com/linux/ubuntu/gpg |" + sudo("apt-key add -"))
            if processor == "amd64" or processor == "x86_64":
                sshsudo("""
                    add-apt-repository \
                    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
                    $(lsb_release -cs) \
                    stable"
                    """)

            elif processor == "armhf":
                sshsudo("""
                    add-apt-repository \
                    "deb [arch=armhf] https://download.docker.com/linux/ubuntu \
                    $(lsb_release -cs) \
                    stable"
                     """)

            elif processor == "s390x":
                sshsudo("""
                    add-apt-repository \
                    "deb [arch=s390x] https://download.docker.com/linux/ubuntu \
                    $(lsb_release -cs) \
                    stable"
                      """)

            sshsudo("apt-get update")
            sshsudo("apt-get install docker-ce")
            # sudo apt-get install docker-ce=<VERSION>  On production systems, you should install a specific version of Docker CE instead of always using the latest
        else:
            exit()

    elif os_market_name == "CentOS":
        # https://docs.docker.com/engine/installation/linux/docker-ce/centos/#prerequisites
        sshsudo(
            """
            yum install -y yum-utils \
            device-mapper-persistent-data \
            lvm2
            """
        )
        sshsudo(
            """
            yum-config-manager \
            --add-repo \
            https://download.docker.com/linux/centos/docker-ce.repo
            """
        )
        ssh_client.exec_command("yum install docker-ce")


def is_target_can_access_internet():
    stdin, stdout, stderr = ssh_client.exec_command("nc -z download.docker.com 80")
    if stdout.read() == "":
        return False
    return True


def install_docker_compose():
    
    url = "https://github.com/docker/compose/releases/latest"
    response = urlopen(url)
    soup = BeautifulSoup(response)
    regx = re.compile("docker-compose-{s}-{m}".format(s=system, m=machine))
    anchors = soup.findAll('a', href=regx)
    length = len(anchors)
    if 0 == length:
        log.warn("Latest docker compose version unfound,exit;")
        exit()
    last = anchors[length - 1]
    last_href = last["href"]
    basename = os.path.basename(last_href)
    log.info("Latest docker compose version found:{0}".format(basename))
    lastlink = urljoin(url, last_href)
    relpath = urlsplit(url).path[1:]
    filepath = host_home(os.path.join(
        "docker-compose", os.path.normpath(relpath), basename))
    remote_file_path = remote_home(basename)
    remote_path = os.path.dirname(remote_file_path)
    stdin, stdout, stderr = ssh_client.exec_command(
        "stat -c %s {0}".format(remote_file_path))
    filesize = stdout.read().strip()
    def install():
        sshsudo(
            "cp {0} /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose".format(remote_file_path))
        log.info("docker compose successfully installed!")
    if filesize == "":
        # docker compose bin not downloaded on target
        pass
    else:
        if os.path.exists(filepath) and int(filesize) == os.path.getsize(filepath):
            install()
            return
        else:
            # partial docker tarball on target
            pass
  
    def callback():
            ssh_client.exec_command("mkdir -p {0}".format(remote_path))
            try:
                scp_client.put(filepath, recursive=True, remote_path=remote_file_path)
            except scp.SCPException as e:
                if e.message == 'Timout waiting for scp response':
                    pass
            install()

    if not os.path.exists(filepath):
        log.info("Host has not docker compose")
        if not is_host_can_access_github():
            exit()
        _reporthook = partial(reporthook, callback,filepath)
        mkdir_p(os.path.dirname(filepath))

        # for i in xrange(3):
        try:
            # stat -c %s docker_installer_resource/docker/linux/static/stable/x86_64/docker-17.09.0-ce.tgz
            urlretrieve(lastlink, filepath, _reporthook)
        # except socket.timeout:
        #     pass
        # except IOError as e:
        #     log.error(e.strerror)
        #     raise e
        except Exception as e:
            log.error(e)
            raise e
        # finally:
        #     pass
            # urllib.urlcleanup()
            # ssh_client.close()
    else:
        if get_remote_content_size(lastlink) == os.path.getsize(filepath):
            log.info("Host already has docker compose")
            callback()
        else:
            # partial docker compose on host
            pass

def precheck_install_docker_offline():
    stdin, stdout, stderr = ssh_client.exec_command("iptables -V")
    found = re.findall("\d+\.\d+", stdout.read())
    if len(found):
        ipv = float(found[0])
    else:
        ssh_client.exec_command("apt-get update && apt-get install -y iptables")
        ipv = 1.4
    stdin, stdout, stderr = ssh_client.exec_command("git --version")
    gitvs = stdout.read()
    gitvg = re.findall("\d+\.\d+", gitvs)
    if gitvs == '' or len(gitvg) == 0 or gitvg[0] < 1.7:
        # git install
        ensure_git()
    stdin, stdout, stderr = ssh_client.exec_command(
        "python -c 'import platform;print \"萌\".join(platform.architecture())'")
    bits, linkage = stdout.read().split(u"萌")
    if (ipv >= 1.4 and bits == "64bit"):
        install_docker_offline()
    else:
        log.error("Not fit prerequires!")
        exit()

def install_docker():   
    if system in SUPPORTED_PLATFORM:
        if is_target_can_access_internet():
            install_docker_online()
        else:
            log.info("Target has no internet connection")
            precheck_install_docker_offline()
    else:  # static
        log.error("Not supported platform!")

def args_parse():
    global args
    parser = argparse.ArgumentParser(prog='docker_installer',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(
                                         'install docker to remote machine through ssh automatically.\ndocker_installer <ssh ip> <ssh port> <ssh user> --password <ssh password> --log <log level>')
                                     )
    parser.add_argument('ip', nargs="?",type=str)
    parser.add_argument('port', nargs="?",type=int,default=22)
    parser.add_argument('user', nargs="?",type=str)
    parser.add_argument('--password', dest="password",nargs="?",type=str)
    parser.add_argument('--version', action='version',
                        version='%(prog)s {0}'.format(__version__))
    parser.add_argument('--log', dest="log", default="ERROR",
                        metavar="string", action='store', type=str)
    parser.add_argument('--local', dest="local", default=False,action='store_true', help='install to local\ndocker_installer --password <rootpassword> --local')
    args = parser.parse_args()

def main():
    socket.setdefaulttimeout(10)
    args_parse()
    init()
    docker_installed = check_if_docker_installed()
    if not docker_installed:
        install_docker()
    compose_installed = check_if_docker_compose_installed()
    if not compose_installed:
        install_docker_compose()

if __name__ =='__main__':
    main()
  

