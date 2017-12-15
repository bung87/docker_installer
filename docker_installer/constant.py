# https://docs.docker.com/engine/installation/#server
# docker ce
SUPPORTED_ARCH = {
    "Ubuntu": ['amd64', 'x86_64', 'armhf', 's390x'],
    "Debian": ['amd64', 'x86_64', 'armhf'],
    "CentOS": ['amd64', 'x86_64'],
    "Fedora": ['amd64', 'x86_64']
    #  CentOS 7
}

SUPPORTED_PLATFORM = ['Darwin', 'Windows',
                     'Linux']

BASE_DIR_NAME = "docker_installer_resource"
