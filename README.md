# docker_installer  

install docker to remote machine through ssh automatically.  

## Installation
`pip install git+https://github.com/bung87/docker_installer`  
install [pip](https://pip.pypa.io/en/latest/installing/) first if python version less than 2.7.9

## docker_installer 是什么?  

install **docker** to remote machine through ssh automatically.  

if remote machine has internet connection, **docker_installer** will add docker package repository as needs and install docker through system package manager.

if remote machine can not access internet **docker_installer** will download the latest stable docker tarball and **scp** the tarball to remote and install docker.  

if remote machine has no **git** installed or git version less than 1.7 this program also download the latest git tarball and **scp** the tarball to remote and install git.


## 如何使用？  

`docker_installer <ssh ip> <ssh port> <ssh user> --password <rootpassword> --log <log level>`

--log is optional.supported log level CRITICAL,ERROR,WARNING,INFO,DEBUG,NOTSET default is NOTSET.

## download data store dirctory

`~/docker_installer_resource`

## tested 
execute environment:  

Python 2.7.10 

remote environment:  

Ubuntu 14.04.1 without  internet connection

