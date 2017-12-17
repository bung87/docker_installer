import platform,sys;
if sys.version_info < (3,3):
    uname = platform.uname()
else:
    uname = platform.uname()
    uname = (uname.system, uname.node, uname.release, uname.version, uname.machine, uname.processor)
print(u"萌".join(uname))