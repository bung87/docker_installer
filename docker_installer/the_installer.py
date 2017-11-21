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
import urlparse
import urllib2
import urllib
import socket
if sys.version_info < (3,):
    from urllib import urlretrieve
    from BeautifulSoup import BeautifulSoup
else:
    from urllib.request import urlretrieve
    from bs4 import BeautifulSoup
from functools import partial
import ssl
from functools import wraps
try:
    import httplib
except:
    import http.client as httplib


# ssl.PROTOCOL_SSLv23 = ssl.PROTOCOL_TLSv1
# log,ssh,loginpassword,HOST_HOME,REMOTE_HOME,processor = None

def init():
    global log, ssh_client, loginpassword, HOST_HOME, REMOTE_HOME, system, processor,machine
    log = logging.getLogger(__name__)
    loglevel = "ERROR"
    argvlen = len(sys.argv)
    if argvlen == 5:
        (script, server, port, user, loginpassword) = sys.argv
    elif argvlen == 6:
        (script, server, port, user, loginpassword, logarg) = sys.argv
        loglevel = logarg.split("=")[1]

    numeric_level = getattr(logging, loglevel.upper(), None)

    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(level=numeric_level)
    port = int(port)
    ssh_client = createSSHClient(server, port, user, loginpassword)
    HOST_HOME = os.path.expanduser('~')

    stdin, stdout, stderr = ssh_client.exec_command(
        "python -c 'import platform;print \"萌\".join(platform.uname())'")

    (system, node, release, version, machine, processor) = stdout.read().split("萌")
    processor = processor.strip()
    stdin, stdout, stderr = ssh_client.exec_command("echo $HOME")
    REMOTE_HOME = stdout.read().strip()


def sudo(e):
    return "echo {loginpassword} | sudo -S {e}".format(loginpassword=loginpassword, e=e)


def progress(filename, size, sent):
    percent = float(sent) / size
    percent = round(percent * 100, 2)
    log.info("Sent %s %d of %d bytes (%0.2f%%)" %
             (filename, sent, size, percent))


def check_if_docker_installed():
    stdin, stdout, stderr = ssh_client.exec_command("docker -v")

    if stdout.read() != "":
        log.info("Target already has docker installed!")
        return True
    return False

def check_if_docker_compose_installed():
    stdin, stdout, stderr = ssh_client.exec_command("docker-compose -v")

    if stdout.read() != "":
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
    scp = SCPClient(ssh_client.get_transport(), progress=progress)
    url = "https://www.kernel.org/pub/software/scm/git/"
    response = urllib.urlopen(url)
    soup = BeautifulSoup(response)
    regx = re.compile("^git-([0-9\.]+)\.tar\.gz$")
    anchors = soup.findAll('a', text=regx)
    length = len(anchors)
    last = anchors[length - 1]
    last_href = last["href"]
    basename = os.path.basename(last_href)
    log.info("latest git version found:{0}".format(basename))
    lastlink = urlparse.urljoin(url, last_href)
    filepath = host_home(basename)
    extract_dir = os.path.splitext(basename)[0]
    ver = regx.match(basename).group(1)

    def callback():
        remote_file_path = remote_home(basename)
        remote_path = os.path.dirname(remote_file_path)
        scp.put(filepath, recursive=True, remote_path=remote_file_path)
        ssh_client.exec_command(
            "cd {0} && tar -xzf {1}".format(remote_path, basename))
        sshsudo(
            "cd {0} && make prefix=/usr && make prefix=/usr install".format(os.path.join(remote_path, extract_dir)))
    if not os.path.exists(filepath):
        log.info("download git")
        _reporthook = partial(reporthook, callback)
        urlretrieve(lastlink, filepath, _reporthook)
    else:
        if get_remote_content_size(lastlink) == os.path.getsize(filepath):
            log.info("Host already has git tarball")
            callback()
        else:
            # partial git tarball on host
            pass


def reporthook(callback, bytes_so_far, chunk_size, total_size):
    percent = float(bytes_so_far) / total_size
    percent = round(percent * 100, 2)
    log.info("Downloaded %d of %d bytes (%0.2f%%)" %
             (bytes_so_far, total_size, percent))
    if bytes_so_far >= total_size:
        callback()


def install_docker_offline():
    log.info("install_docker_offline")
    scp_client = SCPClient(ssh_client.get_transport(), progress=progress)
    url = "https://download.docker.com/linux/static/stable/{arch}/".format(
        arch=processor)
    log.info("Fetch docker download index page:{0}".format(url))
    for i in xrange(3):
        try:
            response = urllib.urlopen(url)
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
    lastlink = urlparse.urljoin(url, last_href)
    relpath = urlparse.urlsplit(url).path[1:]
    filepath = host_home(os.path.join(
        "docker", os.path.normpath(relpath), basename))
    remote_file_path = remote_home(basename)
    remote_path = os.path.dirname(remote_file_path)
    stdin, stdout, stderr = ssh_client.exec_command(
        "stat -c %s {0}".format(remote_file_path))
    filesize = stdout.read().strip()
    if filesize == "":
        # docker tarball not downloaded on target
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
    if not os.path.exists(filepath):
        log.info("Host has not docker tarball")
        if not is_host_can_access_docker():
            exit

        _reporthook = partial(reporthook, callback)
        mkdir_p(os.path.dirname(filepath))

        for i in xrange(3):
            try:
                # stat -c %s docker_installer_resource/docker/linux/static/stable/x86_64/docker-17.09.0-ce.tgz
                urlretrieve(lastlink, filepath, _reporthook)
            except socket.timeout:
                pass
            except IOError as e:
                log.error(e.strerror)
                raise e
            except Exception as e:
                log.error(e)
            finally:
                urllib.urlcleanup()
                ssh_client.close()

    else:
        if get_remote_content_size(lastlink) == os.path.getsize(filepath):
            log.info("Host already has docker tarball")
            callback()
        else:
            # partial docker tarball on host
            pass


def install_docker_online():
    log.info("install_docker_online")
    if system == "Ubuntu":
        # https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/
        if processor in SUPPORTED_ARCH[system]:
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

    elif system == "CentOS":
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
    scp_client = SCPClient(ssh_client.get_transport(), progress=progress)
    url = "https://github.com/docker/compose/releases/latest"
    response = urllib.urlopen(url)
    soup = BeautifulSoup(response)
    regx = re.compile("docker-compose-{s}-{m}".format(s=system, m=machine))
    anchors = soup.findAll('a', href=regx)
    length = len(anchors)
    if 0 == length:
        log.warn("Latest docker compose version unfound,exit;")
        exit;
    last = anchors[length - 1]
    last_href = last["href"]
    basename = os.path.basename(last_href)
    log.info("Latest docker compose version found:{0}".format(basename))
    lastlink = urlparse.urljoin(url, last_href)
    relpath = urlparse.urlsplit(url).path[1:]
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
        _reporthook = partial(reporthook, callback)
        mkdir_p(os.path.dirname(filepath))

        for i in xrange(3):
            try:
                # stat -c %s docker_installer_resource/docker/linux/static/stable/x86_64/docker-17.09.0-ce.tgz
                urlretrieve(lastlink, filepath, _reporthook)
            except socket.timeout:
                pass
            except IOError as e:
                log.error(e.strerror)
                raise e
            except Exception as e:
                log.error(e)
            finally:
                urllib.urlcleanup()
                ssh_client.close()
    else:
        if get_remote_content_size(lastlink) == os.path.getsize(filepath):
            log.info("Host already has docker compose")
            callback()
        else:
            # partial docker compose on host
            pass

def install_docker():   
    if system in SUPPORTED_PLATFORM:
        if is_target_can_access_internet():
            install_docker_online()
        else:
            log.info("Target has no internet connection")

    else:  # static
        stdin, stdout, stderr = ssh_client.exec_command("iptables -V")
        ipv = float(re.findall("\d+\.\d+", stdout.read())[0])
        stdin, stdout, stderr = ssh_client.exec_command("git --version")
        gitvs = stdout.read()
        if gitvs == '':
            # git install
            stdout = ensure_git()
        gitv = float(re.findall("\d+\.\d+", gitvs)[0])
        stdin, stdout, stderr = ssh_client.exec_command(
            "python -c 'import platform;print \"萌\".join(platform.architecture())'")
        bits, linkage = stdout.read().split("萌")
        if (ipv >= 1.4 and gitv >= 1.7 and bits == "64bit"):
            install_docker_offline()
        else:
            exit

def main():
    socket.setdefaulttimeout(10)
    init()
    docker_installed = check_if_docker_installed()
    if not docker_installed:
        install_docker()
    compose_installed = check_if_docker_compose_installed()
    if not compose_installed:
        install_docker_compose()

    
  

